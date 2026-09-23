from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import HangRail, RailPlacement, Store, WorkOrder
from app.schemas.schemas import (
    ExpressFlagUpdate,
    ExpressZoneUpdate,
    HangRequest,
    OccupancyOut,
    OccupancySeg,
    OrderOut,
    PickupRequest,
    RailOut,
    StoreOut,
)
from app.services.rail_engine import Segment, first_fit

api_router = APIRouter()

_EPS = 1e-9


def rail_express_zone(rail: HangRail) -> Segment | None:
    if rail.express_zone_start_cm is None or rail.express_zone_end_cm is None:
        return None
    return Segment(rail.express_zone_start_cm, rail.express_zone_end_cm)


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/stores", response_model=list[StoreOut])
def stores(db: Session = Depends(get_db)):
    return db.scalars(select(Store).order_by(Store.id)).all()


@api_router.get("/rails", response_model=list[RailOut])
def rails(db: Session = Depends(get_db)):
    return db.scalars(select(HangRail).order_by(HangRail.id)).all()


@api_router.get("/orders", response_model=list[OrderOut])
def orders(db: Session = Depends(get_db)):
    return db.scalars(select(WorkOrder).order_by(WorkOrder.id.desc())).all()


@api_router.put("/rails/{rail_id}/express-zone", response_model=RailOut)
def set_express_zone(rail_id: int, body: ExpressZoneUpdate, db: Session = Depends(get_db)):
    rail = db.get(HangRail, rail_id)
    if not rail:
        raise HTTPException(404, "挂杆不存在")
    if body.start_cm is None and body.end_cm is None:
        rail.express_zone_start_cm = None
        rail.express_zone_end_cm = None
        db.commit()
        db.refresh(rail)
        return rail
    if body.start_cm is None or body.end_cm is None:
        raise HTTPException(400, "专区起止需同时提供")
    if body.start_cm < 0 or body.end_cm <= body.start_cm or body.end_cm > rail.length_cm + _EPS:
        raise HTTPException(400, "专区起止非法或越过杆长")
    rail.express_zone_start_cm = body.start_cm
    rail.express_zone_end_cm = body.end_cm
    db.commit()
    db.refresh(rail)
    return rail


@api_router.post("/orders/{order_id}/express", response_model=OrderOut)
def set_express_flag(order_id: int, body: ExpressFlagUpdate, db: Session = Depends(get_db)):
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
        express_zone_start_cm=rail.express_zone_start_cm,
        express_zone_end_cm=rail.express_zone_end_cm,
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

    # 预取每根杆的占用段
    rail_gaps: list[tuple[HangRail, list[Segment]]] = []
    for rail in rails:
        active = db.scalars(
            select(RailPlacement).where(RailPlacement.rail_id == rail.id, RailPlacement.active == 1)
        ).all()
        rail_gaps.append((rail, [Segment(p.start_cm, p.end_cm) for p in active]))

    is_express = bool(order.is_express)

    def try_place(zones_first: bool):
        # 加急工单第一趟只尝试各杆专区；第二趟在各杆全杆扫描（first_fit 内部
        # 仍会先查专区，但专区已满时自然落到专区外）。
        for rail, occupied in rail_gaps:
            zone = rail_express_zone(rail)
            place = first_fit(
                rail.length_cm,
                occupied,
                order.length_cm,
                express_zone=zone,
                is_express=is_express if zones_first else False,
            )
            if place is None:
                continue
            # zones_first 趟必须确保落点确实在专区内（无专区的杆跳过本趟）
            if zones_first and (zone is None or place.start_cm < zone.start_cm or place.end_cm > zone.end_cm + _EPS):
                continue
            db.add(
                RailPlacement(
                    rail_id=rail.id,
                    order_id=order.id,
                    start_cm=place.start_cm,
                    end_cm=place.end_cm,
                )
            )
            return rail
        return None

    chosen = try_place(zones_first=True) if is_express else None
    if chosen is None:
        chosen = try_place(zones_first=False)
    if chosen is not None:
        order.status = "hung"
        order.hung_at = datetime.utcnow()
        db.commit()
        db.refresh(order)
        return order

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
