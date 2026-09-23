from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Store(Base):
    __tablename__ = "stores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    rails: Mapped[list["HangRail"]] = relationship(back_populates="store")


class HangRail(Base):
    __tablename__ = "hang_rails"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    label: Mapped[str] = mapped_column(String(40))
    length_cm: Mapped[float] = mapped_column(Float)
    # 快递专区半开区间 [express_zone_start_cm, express_zone_end_cm)，NULL 表示未划专区
    express_zone_start_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    express_zone_end_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    store: Mapped[Store] = relationship(back_populates="rails")
    placements: Mapped[list["RailPlacement"]] = relationship(back_populates="rail")


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    ticket_code: Mapped[str] = mapped_column(String(40), unique=True)
    garment_name: Mapped[str] = mapped_column(String(80))
    length_cm: Mapped[float] = mapped_column(Float)
    is_express: Mapped[int] = mapped_column(Integer, default=0)  # 1 = 快递加急
    status: Mapped[str] = mapped_column(String(20), default="ready")  # ready/hung/picked/overdue
    due_at: Mapped[datetime] = mapped_column(DateTime)
    hung_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RailPlacement(Base):
    __tablename__ = "rail_placements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rail_id: Mapped[int] = mapped_column(ForeignKey("hang_rails.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"))
    start_cm: Mapped[float] = mapped_column(Float)
    end_cm: Mapped[float] = mapped_column(Float)
    active: Mapped[int] = mapped_column(Integer, default=1)
    rail: Mapped[HangRail] = relationship(back_populates="placements")
