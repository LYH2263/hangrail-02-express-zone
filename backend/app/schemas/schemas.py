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
    express_start_cm: float | None = None
    express_end_cm: float | None = None
    model_config = {"from_attributes": True}


class RailZoneIn(BaseModel):
    # 同时为 None（或不传）表示清除专区；否则必须给出合法半开区间
    express_start_cm: float | None = None
    express_end_cm: float | None = None


class OrderOut(BaseModel):
    id: int
    store_id: int
    ticket_code: str
    garment_name: str
    length_cm: float
    status: str
    is_express: bool = False
    due_at: datetime
    hung_at: datetime | None
    model_config = {"from_attributes": True}


class OrderIn(BaseModel):
    ticket_code: str
    garment_name: str
    length_cm: float
    is_express: bool = False
    store_id: int | None = None
    due_in_hours: int = 48


class ExpressFlagIn(BaseModel):
    is_express: bool


class HangRequest(BaseModel):
    order_id: int
    rail_id: int | None = None


class PickupRequest(BaseModel):
    ticket_code: str


class OccupancySeg(BaseModel):
    order_id: int
    ticket_code: str
    garment_name: str
    is_express: bool = False
    start_cm: float
    end_cm: float


class OccupancyOut(BaseModel):
    rail_id: int
    label: str
    length_cm: float
    express_start_cm: float | None = None
    express_end_cm: float | None = None
    segments: list[OccupancySeg]
