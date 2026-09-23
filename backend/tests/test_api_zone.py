import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.database import Base, get_db
from app.models.models import HangRail, RailPlacement, Store, WorkOrder
from fastapi import FastAPI

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    store = Store(name="测试店")
    db.add(store)
    db.flush()
    # B 杆 160cm，前 60cm 专区；专区内已有加急衬衫 0-25，专区外 60-100 有普通风衣
    b = HangRail(store_id=store.id, label="B 杆", length_cm=160,
                 express_start_cm=0, express_end_cm=60)
    # A 杆 200cm，无专区
    a = HangRail(store_id=store.id, label="A 杆", length_cm=200)
    db.add_all([a, b])
    db.flush()
    shirt = WorkOrder(store_id=store.id, ticket_code="E001", garment_name="加急衬衫",
                      length_cm=25, status="hung", is_express=1)
    coat = WorkOrder(store_id=store.id, ticket_code="N001", garment_name="风衣",
                     length_cm=40, status="hung", is_express=0)
    db.add_all([shirt, coat])
    db.flush()
    db.add_all([
        RailPlacement(rail_id=b.id, order_id=shirt.id, start_cm=0, end_cm=25),
        RailPlacement(rail_id=b.id, order_id=coat.id, start_cm=60, end_cm=100),
    ])
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    def _get_db():
        s = TestingSessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def _add_order(client, code, name, length, is_express):
    r = client.post("/api/orders", json={
        "ticket_code": code, "garment_name": name,
        "length_cm": length, "is_express": is_express,
        "store_id": 1,
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_normal_order_skips_zone_gap(client):
    """普通羽绒服 30cm 本可放入专区空隙 [25,60)，必须跳过专区挂到 100。"""
    oid = _add_order(client, "N002", "羽绒服", 30, False)
    r = client.post("/api/hang", json={"order_id": oid, "rail_id": 2})
    assert r.status_code == 200, r.text
    segs = client.get("/api/occupancy/2").json()["segments"]
    mine = next(s for s in segs if s["ticket_code"] == "N002")
    assert mine["start_cm"] == 100
    assert mine["end_cm"] == 130


def test_express_order_lands_in_zone(client):
    """加急短衣 20cm 落入专区空隙 [25,45)。"""
    oid = _add_order(client, "E002", "加急短裙", 20, True)
    r = client.post("/api/hang", json={"order_id": oid, "rail_id": 2})
    assert r.status_code == 200, r.text
    segs = client.get("/api/occupancy/2").json()["segments"]
    mine = next(s for s in segs if s["ticket_code"] == "E002")
    assert mine["start_cm"] == 25
    assert mine["end_cm"] == 45
    assert mine["is_express"] is True


def test_invalid_zone_rejected(client):
    r = client.put("/api/rails/2/zone", json={"express_start_cm": 0, "express_end_cm": 999})
    assert r.status_code == 422
    r = client.put("/api/rails/2/zone", json={"express_start_cm": 80, "express_end_cm": 60})
    assert r.status_code == 422


def test_zone_conflict_with_normal_placement_rejected(client):
    # 新专区 [90, 120) 与普通风衣 60-100 重叠 → 拒绝
    r = client.put("/api/rails/2/zone", json={"express_start_cm": 90, "express_end_cm": 120})
    assert r.status_code == 409


def test_rail_without_zone_fully_usable(client):
    oid = _add_order(client, "N003", "普通外套", 30, False)
    r = client.post("/api/hang", json={"order_id": oid, "rail_id": 1})
    assert r.status_code == 200, r.text
    segs = client.get("/api/occupancy/1").json()["segments"]
    mine = next(s for s in segs if s["ticket_code"] == "N003")
    assert mine["start_cm"] == 0


def test_express_auto_prefers_zoned_rail_across_rails(client):
    """不指定杆：A 杆（无专区、全空）排前面，加急衣仍应跨杆优先落入 B 杆专区。"""
    oid = _add_order(client, "E003", "加急马甲", 20, True)
    r = client.post("/api/hang", json={"order_id": oid})
    assert r.status_code == 200, r.text
    segs = client.get("/api/occupancy/2").json()["segments"]
    mine = next(s for s in segs if s["ticket_code"] == "E003")
    assert mine["start_cm"] == 25
    # A 杆保持全空
    assert client.get("/api/occupancy/1").json()["segments"] == []


def test_toggle_express_then_zone_priority(client):
    oid = _add_order(client, "N004", "短衣", 20, False)
    r = client.patch(f"/api/orders/{oid}/express", json={"is_express": True})
    assert r.status_code == 200
    assert r.json()["is_express"] is True
    r = client.post("/api/hang", json={"order_id": oid, "rail_id": 2})
    assert r.status_code == 200
    mine = next(s for s in client.get("/api/occupancy/2").json()["segments"]
                if s["ticket_code"] == "N004")
    assert mine["start_cm"] == 25
