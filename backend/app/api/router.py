from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import HangRail, RailPlacement, Store, WorkOrder
from app.schemas.schemas import (
    ExpressFlagIn,
    HangRequest,
    OccupancyOut,
    OccupancySeg,
    OrderIn,
    OrderOut,
    PickupRequest,
    RailOut,
    RailZoneIn,
    StoreOut,
)
from app.services.rail_engine import Segment, first_fit, valid_zone

api_router = APIRouter()


def _zone_of(rail: HangRail) -> Segment | None:
    if rail.express_start_cm is None or rail.express_end_cm is None:
        return None
    return Segment(rail.express_start_cm, rail.express_end_cm)


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/stores", response_model=list[StoreOut])
def stores(db: Session = Depends(get_db)):
    return db.scalars(select(Store).order_by(Store.id)).all()


@api_router.get("/rails", response_model=list[RailOut])
def rails(db: Session = Depends(get_db)):
    return db.scalars(select(HangRail).order_by(HangRail.id)).all()


@api_router.put("/rails/{rail_id}/zone", response_model=RailOut)
def update_rail_zone(rail_id: int, body: RailZoneIn, db: Session = Depends(get_db)):
    rail = db.get(HangRail, rail_id)
    if not rail:
        raise HTTPException(404, "挂杆不存在")
    start, end = body.express_start_cm, body.express_end_cm
    clearing = start is None and end is None
    if not clearing and not valid_zone(rail.length_cm, start, end):
        raise HTTPException(
            422,
            "专区区间非法：需满足 0 ≤ 起点 < 终点 ≤ 杆长（半开区间，单位 cm）",
        )
    # 已有占位与新区间冲突时拒绝，避免普通衣被专区吞掉
    if not clearing:
        active = db.scalars(
            select(RailPlacement).where(
                RailPlacement.rail_id == rail_id, RailPlacement.active == 1
            )
        ).all()
        zone = Segment(start, end)
        for p in active:
            order = db.get(WorkOrder, p.order_id)
            if order and not order.is_express:
                seg = Segment(p.start_cm, p.end_cm)
                if seg.start_cm < zone.end_cm and seg.end_cm > zone.start_cm:
                    raise HTTPException(409, "专区与杆上普通工单占位冲突，请先取件或改划区间")
    rail.express_start_cm = None if clearing else start
    rail.express_end_cm = None if clearing else end
    db.commit()
    db.refresh(rail)
    return rail


@api_router.get("/orders", response_model=list[OrderOut])
def orders(db: Session = Depends(get_db)):
    return db.scalars(select(WorkOrder).order_by(WorkOrder.id.desc())).all()


@api_router.post("/orders", response_model=OrderOut)
def create_order(body: OrderIn, db: Session = Depends(get_db)):
    if body.length_cm <= 0:
        raise HTTPException(422, "衣长必须为正数")
    if db.scalar(select(WorkOrder.id).where(WorkOrder.ticket_code == body.ticket_code)):
        raise HTTPException(409, "票号已存在")
    if body.store_id is not None:
        store = db.get(Store, body.store_id)
    else:
        store = db.scalar(select(Store).order_by(Store.id))
    if not store:
        raise HTTPException(404, "门店不存在")
    order = WorkOrder(
        store_id=store.id,
        ticket_code=body.ticket_code,
        garment_name=body.garment_name,
        length_cm=body.length_cm,
        status="ready",
        is_express=1 if body.is_express else 0,
        due_at=datetime.utcnow() + timedelta(hours=body.due_in_hours),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@api_router.patch("/orders/{order_id}/express", response_model=OrderOut)
def set_order_express(order_id: int, body: ExpressFlagIn, db: Session = Depends(get_db)):
    order = db.get(WorkOrder, order_id)
    if not order:
        raise HTTPException(404, "工单不存在")
    order.is_express = 1 if body.is_express else 0
    db.commit()
    db.refresh(order)
    return order


@api_router.get("/occupancy/{rail_id}", response_model=OccupancyOut)
def occupancy(rail_id: int, db: Session = Depends(get_db)):
    rail = db.get(HangRail, rail_id)
    if not rail:
        raise HTTPException(404, "挂杆不存在")
    placements = db.scalars(
        select(RailPlacement).where(RailPlacement.rail_id == rail_id, RailPlacement.active == 1)
    ).all()
    segs = []
    for p in placements:
        order = db.get(WorkOrder, p.order_id)
        if not order:
            continue
        segs.append(
            OccupancySeg(
                order_id=order.id,
                ticket_code=order.ticket_code,
                garment_name=order.garment_name,
                is_express=bool(order.is_express),
                start_cm=p.start_cm,
                end_cm=p.end_cm,
            )
        )
    segs.sort(key=lambda s: s.start_cm)
    return OccupancyOut(
        rail_id=rail.id,
        label=rail.label,
        length_cm=rail.length_cm,
        express_start_cm=rail.express_start_cm,
        express_end_cm=rail.express_end_cm,
        segments=segs,
    )


@api_router.post("/hang", response_model=OrderOut)
def hang(body: HangRequest, db: Session = Depends(get_db)):
    order = db.get(WorkOrder, body.order_id)
    if not order:
        raise HTTPException(404, "工单不存在")
    if order.status not in ("ready", "overdue"):
        raise HTTPException(400, "工单状态不可上杆")
    rail_q = select(HangRail).where(HangRail.store_id == order.store_id)
    if body.rail_id:
        rail_q = rail_q.where(HangRail.id == body.rail_id)
    rails = db.scalars(rail_q.order_by(HangRail.id)).all()
    if not rails:
        raise HTTPException(404, "无可用挂杆")

    def rail_snapshot(rail: HangRail) -> tuple[list[Segment], Segment | None]:
        active = db.scalars(
            select(RailPlacement).where(RailPlacement.rail_id == rail.id, RailPlacement.active == 1)
        ).all()
        return [Segment(p.start_cm, p.end_cm) for p in active], _zone_of(rail)

    def place_on(rail: HangRail, place) -> OrderOut:
        db.add(
            RailPlacement(
                rail_id=rail.id,
                order_id=order.id,
                start_cm=place.start_cm,
                end_cm=place.end_cm,
            )
        )
        order.status = "hung"
        order.hung_at = datetime.utcnow()
        db.commit()
        db.refresh(order)
        return order

    # 加急工单第一轮：跨杆只看专区，优先把加急衣收进任意一根杆的专区
    if order.is_express:
        for rail in rails:
            occupied, zone = rail_snapshot(rail)
            place = first_fit(
                rail.length_cm, occupied, order.length_cm,
                express_zone=zone, is_express=True, zone_only=True,
            )
            if place is not None:
                return place_on(rail, place)

    # 现网规则：普通衣跳过专区空隙；加急衣专区已放不下，回退扫专区外空隙
    for rail in rails:
        occupied, zone = rail_snapshot(rail)
        place = first_fit(
            rail.length_cm,
            occupied,
            order.length_cm,
            express_zone=zone,
            is_express=bool(order.is_express),
        )
        if place is not None:
            return place_on(rail, place)

    raise HTTPException(409, "挂杆空间不足")


@api_router.post("/pickup", response_model=OrderOut)
def pickup(body: PickupRequest, db: Session = Depends(get_db)):
    order = db.scalar(select(WorkOrder).where(WorkOrder.ticket_code == body.ticket_code))
    if not order:
        raise HTTPException(404, "取件码无效")
    if order.status != "hung":
        raise HTTPException(400, "工单未在挂杆上")
    placements = db.scalars(
        select(RailPlacement).where(RailPlacement.order_id == order.id, RailPlacement.active == 1)
    ).all()
    for p in placements:
        p.active = 0
    order.status = "picked"
    db.commit()
    db.refresh(order)
    return order


@api_router.post("/overdue/scan", response_model=list[OrderOut])
def overdue_scan(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    hung = db.scalars(select(WorkOrder).where(WorkOrder.status == "hung")).all()
    marked = []
    for o in hung:
        if o.due_at < now:
            o.status = "overdue"
            marked.append(o)
    ready = db.scalars(select(WorkOrder).where(WorkOrder.status == "ready")).all()
    for o in ready:
        if o.due_at < now:
            o.status = "overdue"
            marked.append(o)
    db.commit()
    return marked


@api_router.get("/overdue", response_model=list[OrderOut])
def overdue_list(db: Session = Depends(get_db)):
    return db.scalars(select(WorkOrder).where(WorkOrder.status == "overdue").order_by(WorkOrder.due_at)).all()
