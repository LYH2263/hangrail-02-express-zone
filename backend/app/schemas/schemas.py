from datetime import datetime
from pydantic import BaseModel


class StoreOut(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class RailOut(BaseModel):
    id: int
    store_id: int
    label: str
    length_cm: float
    express_zone_start_cm: float | None
    express_zone_end_cm: float | None
    model_config = {"from_attributes": True}


class ExpressZoneUpdate(BaseModel):
    # 两个字段同时为 null 表示清除专区
    start_cm: float | None = None
    end_cm: float | None = None


class ExpressFlagUpdate(BaseModel):
    is_express: bool


class OrderOut(BaseModel):
    id: int
    store_id: int
    ticket_code: str
    garment_name: str
    length_cm: float
    is_express: bool
    status: str
    due_at: datetime
    hung_at: datetime | None
    model_config = {"from_attributes": True}


class HangRequest(BaseModel):
    order_id: int
    rail_id: int | None = None


class PickupRequest(BaseModel):
    ticket_code: str


class OccupancySeg(BaseModel):
    order_id: int
    ticket_code: str
    garment_name: str
    is_express: bool
    start_cm: float
    end_cm: float


class OccupancyOut(BaseModel):
    rail_id: int
    label: str
    length_cm: float
    express_zone_start_cm: float | None
    express_zone_end_cm: float | None
    segments: list[OccupancySeg]
