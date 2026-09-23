"""API 层测例：专区保存校验 + 种子场景上杆行为。

用 SQLite 内存库替换 get_db，不依赖 Postgres。
"""

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.database import Base, get_db
from app.models.models import HangRail, RailPlacement, Store, WorkOrder


@pytest.fixture()
def client_and_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, TestingSession


def seed_zone_scenario(db):
    """B 杆 [0,60) 专区，风衣占 [60,100)；羽绒服(普通 50cm) 与衬衫(加急 25cm) 待上杆。"""
    store = Store(name="测试店")
    db.add(store)
    db.flush()
    rail = HangRail(
        store_id=store.id,
        label="B 杆",
        length_cm=160,
        express_zone_start_cm=0,
        express_zone_end_cm=60,
    )
    db.add(rail)
    db.flush()
    now = datetime.utcnow()
    coat = WorkOrder(
        store_id=store.id, ticket_code="T-1", garment_name="风衣", length_cm=40,
        status="hung", due_at=now + timedelta(days=1), hung_at=now,
    )
    down = WorkOrder(
        store_id=store.id, ticket_code="T-2", garment_name="羽绒服", length_cm=50,
        status="ready", due_at=now + timedelta(days=1),
    )
    shirt = WorkOrder(
        store_id=store.id, ticket_code="T-3", garment_name="衬衫", length_cm=25,
        is_express=1, status="ready", due_at=now + timedelta(hours=8),
    )
    db.add_all([coat, down, shirt])
    db.flush()
    db.add(RailPlacement(rail_id=rail.id, order_id=coat.id, start_cm=60, end_cm=100))
    db.commit()
    return rail, down, shirt


def test_normal_down_jacket_skips_zone(client_and_db):
    client, Session = client_and_db
    db = Session()
    rail, down, _ = seed_zone_scenario(db)
    rail_id, down_id = rail.id, down.id
    db.close()

    res = client.post("/api/hang", json={"order_id": down_id, "rail_id": rail_id})
    assert res.status_code == 200, res.text

    occ = client.get(f"/api/occupancy/{rail_id}").json()
    seg = next(s for s in occ["segments"] if s["ticket_code"] == "T-2")
    # 普通羽绒服不得占用 [0,60) 专区，落在风衣之后
    assert seg["start_cm"] >= 60
    assert seg["start_cm"] == 100


def test_express_shirt_lands_in_zone(client_and_db):
    client, Session = client_and_db
    db = Session()
    rail, _, shirt = seed_zone_scenario(db)
    rail_id, shirt_id = rail.id, shirt.id
    db.close()

    res = client.post("/api/hang", json={"order_id": shirt_id, "rail_id": rail_id})
    assert res.status_code == 200, res.text

    occ = client.get(f"/api/occupancy/{rail_id}").json()
    seg = next(s for s in occ["segments"] if s["ticket_code"] == "T-3")
    # 加急短衣挂进专区 [0,60)
    assert seg["start_cm"] == 0
    assert seg["end_cm"] == 25


def test_zone_occupancy_fields_present(client_and_db):
    client, Session = client_and_db
    db = Session()
    rail, _, _ = seed_zone_scenario(db)
    rail_id = rail.id
    db.close()

    occ = client.get(f"/api/occupancy/{rail_id}").json()
    assert occ["express_zone_start_cm"] == 0
    assert occ["express_zone_end_cm"] == 60


@pytest.mark.parametrize(
    "start,end",
    [(-1, 60), (60, 60), (80, 60), (0, 161), (100, 200)],
)
def test_invalid_zone_rejected(client_and_db, start, end):
    client, Session = client_and_db
    db = Session()
    store = Store(name="校验店")
    db.add(store)
    db.flush()
    rail = HangRail(store_id=store.id, label="C 杆", length_cm=160)
    db.add(rail)
    db.commit()
    rail_id = rail.id
    db.close()

    res = client.put(f"/api/rails/{rail_id}/express-zone", json={"start_cm": start, "end_cm": end})
    assert res.status_code == 400

    got = client.get("/api/rails").json()
    assert got[0]["express_zone_start_cm"] is None
    assert got[0]["express_zone_end_cm"] is None


def test_zone_half_open_endpoint_allowed(client_and_db):
    client, Session = client_and_db
    db = Session()
    store = Store(name="边界店")
    db.add(store)
    db.flush()
    rail = HangRail(store_id=store.id, label="D 杆", length_cm=160)
    db.add(rail)
    db.commit()
    rail_id = rail.id
    db.close()

    # 半开区间 [0,160)：end 等于杆长合法
    res = client.put(f"/api/rails/{rail_id}/express-zone", json={"start_cm": 0, "end_cm": 160})
    assert res.status_code == 200
    assert res.json()["express_zone_end_cm"] == 160


def test_zone_set_and_clear(client_and_db):
    client, Session = client_and_db
    db = Session()
    store = Store(name="清除店")
    db.add(store)
    db.flush()
    rail = HangRail(store_id=store.id, label="E 杆", length_cm=160)
    db.add(rail)
    db.commit()
    rail_id = rail.id
    db.close()

    res = client.put(f"/api/rails/{rail_id}/express-zone", json={"start_cm": 10, "end_cm": 70})
    assert res.status_code == 200
    assert res.json()["express_zone_start_cm"] == 10

    res = client.put(f"/api/rails/{rail_id}/express-zone", json={"start_cm": None, "end_cm": None})
    assert res.status_code == 200
    assert res.json()["express_zone_start_cm"] is None
    assert res.json()["express_zone_end_cm"] is None


def test_zone_missing_half_rejected(client_and_db):
    client, Session = client_and_db
    db = Session()
    store = Store(name="半残店")
    db.add(store)
    db.flush()
    rail = HangRail(store_id=store.id, label="F 杆", length_cm=160)
    db.add(rail)
    db.commit()
    rail_id = rail.id
    db.close()

    res = client.put(f"/api/rails/{rail_id}/express-zone", json={"start_cm": 10})
    assert res.status_code == 400


def test_express_flag_toggle(client_and_db):
    client, Session = client_and_db
    db = Session()
    store = Store(name="标记店")
    db.add(store)
    db.flush()
    order = WorkOrder(
        store_id=store.id, ticket_code="T-9", garment_name="T恤", length_cm=20,
        status="ready", due_at=datetime.utcnow() + timedelta(days=1),
    )
    db.add(order)
    db.commit()
    order_id = order.id
    db.close()

    res = client.post(f"/api/orders/{order_id}/express", json={"is_express": True})
    assert res.status_code == 200
    assert res.json()["is_express"] is True

    res = client.post(f"/api/orders/{order_id}/express", json={"is_express": False})
    assert res.status_code == 200
    assert res.json()["is_express"] is False


def test_seed_b_rail_zone_and_scenario(client_and_db):
    """种子：B 杆 [0,60) 专区；普通羽绒服跳过专区，加急短衣落入专区。"""
    from app.services.seed import seed_if_empty

    client, Session = client_and_db
    db = Session()
    seed_if_empty(db)
    db.close()

    rails = {r["label"]: r for r in client.get("/api/rails").json()}
    assert rails["B 杆"]["express_zone_start_cm"] == 0
    assert rails["B 杆"]["express_zone_end_cm"] == 60
    assert rails["A 杆"]["express_zone_start_cm"] is None

    orders = {o["ticket_code"]: o for o in client.get("/api/orders").json()}
    b_id = rails["B 杆"]["id"]

    # 普通羽绒服 50cm：专区空着也不得占用
    res = client.post("/api/hang", json={"order_id": orders["HR-2003"]["id"], "rail_id": b_id})
    assert res.status_code == 200, res.text
    occ = client.get(f"/api/occupancy/{b_id}").json()
    seg = next(s for s in occ["segments"] if s["ticket_code"] == "HR-2003")
    assert seg["start_cm"] >= 60

    # 加急短衣（衬衫 25cm）落入专区
    res = client.post("/api/hang", json={"order_id": orders["HR-2006"]["id"], "rail_id": b_id})
    assert res.status_code == 200, res.text
    occ = client.get(f"/api/occupancy/{b_id}").json()
    seg = next(s for s in occ["segments"] if s["ticket_code"] == "HR-2006")
    assert seg["start_cm"] == 0
    assert seg["end_cm"] == 25


def test_express_prefers_zone_rail_over_earlier_rail(client_and_db):
    """同店 A(无专区，排序在前)、B(有专区且专区空)：加急应跨杆优先落入 B 专区。"""
    client, Session = client_and_db
    db = Session()
    store = Store(name="跨杆店")
    db.add(store); db.flush()
    a = HangRail(store_id=store.id, label="A 杆", length_cm=200)
    b = HangRail(store_id=store.id, label="B 杆", length_cm=160,
                 express_zone_start_cm=0, express_zone_end_cm=60)
    db.add_all([a, b]); db.flush()
    now = datetime.utcnow()
    order = WorkOrder(store_id=store.id, ticket_code="X-1", garment_name="加急裙",
                      length_cm=25, is_express=1, status="ready", due_at=now + timedelta(hours=6))
    db.add(order); db.commit()
    b_id, o_id = b.id, order.id
    db.close()

    res = client.post("/api/hang", json={"order_id": o_id})
    assert res.status_code == 200, res.text
    occ = client.get(f"/api/occupancy/{b_id}").json()
    seg = next(s for s in occ["segments"] if s["ticket_code"] == "X-1")
    assert 0 <= seg["start_cm"] and seg["end_cm"] <= 60


def test_express_falls_back_to_rail_without_zone(client_and_db):
    """B 专区放不下 40cm 加急衣，A 杆（无专区）有空：回退到 A 全杆可挂。"""
    client, Session = client_and_db
    db = Session()
    store = Store(name="回退店")
    db.add(store); db.flush()
    a = HangRail(store_id=store.id, label="A 杆", length_cm=200)
    b = HangRail(store_id=store.id, label="B 杆", length_cm=160,
                 express_zone_start_cm=0, express_zone_end_cm=60)
    db.add_all([a, b]); db.flush()
    now = datetime.utcnow()
    blocker = WorkOrder(store_id=store.id, ticket_code="X-0", garment_name="占用衣",
                        length_cm=45, is_express=1, status="hung",
                        due_at=now + timedelta(days=1), hung_at=now)
    target = WorkOrder(store_id=store.id, ticket_code="X-2", garment_name="加急大衣",
                       length_cm=40, is_express=1, status="ready", due_at=now + timedelta(hours=6))
    db.add_all([blocker, target]); db.flush()
    db.add(RailPlacement(rail_id=b.id, order_id=blocker.id, start_cm=0, end_cm=45))
    db.commit()
    a_id, o_id = a.id, target.id
    db.close()

    res = client.post("/api/hang", json={"order_id": o_id})
    assert res.status_code == 200, res.text
    occ = client.get(f"/api/occupancy/{a_id}").json()
    seg = next(s for s in occ["segments"] if s["ticket_code"] == "X-2")
    assert seg["start_cm"] == 0
