from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import HangRail, RailPlacement, Store, WorkOrder


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(Store.id).limit(1)):
        return
    store = Store(name="清风干洗 · 滨江店")
    db.add(store)
    db.flush()
    r1 = HangRail(store_id=store.id, label="A 杆", length_cm=200)
    # B 杆划出前 60cm 作为快递加急专区（半开区间 [0, 60)）
    r2 = HangRail(
        store_id=store.id,
        label="B 杆",
        length_cm=160,
        express_start_cm=0,
        express_end_cm=60,
    )
    db.add_all([r1, r2])
    db.flush()
    now = datetime.utcnow()
    orders = [
        WorkOrder(store_id=store.id, ticket_code="HR-2001", garment_name="羊毛大衣", length_cm=45, status="hung", due_at=now + timedelta(days=1), hung_at=now - timedelta(hours=5)),
        WorkOrder(store_id=store.id, ticket_code="HR-2002", garment_name="西装套装", length_cm=35, status="hung", due_at=now + timedelta(days=2), hung_at=now - timedelta(hours=3)),
        # 普通羽绒服：30cm 本可塞进专区空隙 [25,60)，上杆时必须跳过专区
        WorkOrder(store_id=store.id, ticket_code="HR-2003", garment_name="羽绒服", length_cm=30, status="ready", due_at=now + timedelta(days=1)),
        WorkOrder(store_id=store.id, ticket_code="HR-2004", garment_name="连衣裙", length_cm=30, status="ready", due_at=now - timedelta(days=1)),
        WorkOrder(store_id=store.id, ticket_code="HR-2005", garment_name="风衣", length_cm=40, status="hung", due_at=now - timedelta(hours=12), hung_at=now - timedelta(days=3)),
        # 加急短衣：ready，上杆应优先落入 B 杆专区空隙 [25, 60)
        WorkOrder(store_id=store.id, ticket_code="HR-2006", garment_name="加急短裙", length_cm=20, status="ready", is_express=1, due_at=now + timedelta(hours=12)),
        # 已挂在专区内的快递加急衬衫
        WorkOrder(store_id=store.id, ticket_code="HR-2007", garment_name="加急衬衫", length_cm=25, status="hung", is_express=1, due_at=now + timedelta(hours=10), hung_at=now - timedelta(hours=2)),
    ]
    db.add_all(orders)
    db.flush()
    db.add_all(
        [
            RailPlacement(rail_id=r1.id, order_id=orders[0].id, start_cm=0, end_cm=45),
            RailPlacement(rail_id=r1.id, order_id=orders[1].id, start_cm=45, end_cm=80),
            # B 杆：普通风衣置于专区之外 60-100；加急衬衫挂在专区 0-25
            RailPlacement(rail_id=r2.id, order_id=orders[4].id, start_cm=60, end_cm=100),
            RailPlacement(rail_id=r2.id, order_id=orders[6].id, start_cm=0, end_cm=25),
        ]
    )
    db.commit()
