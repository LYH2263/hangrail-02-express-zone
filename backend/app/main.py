from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


# 轻量迁移：create_all 只建新表，已存在的表需要手动补齐新增列
_ADDED_COLUMNS = (
    "ALTER TABLE hang_rails ADD COLUMN IF NOT EXISTS express_start_cm DOUBLE PRECISION",
    "ALTER TABLE hang_rails ADD COLUMN IF NOT EXISTS express_end_cm DOUBLE PRECISION",
    "ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS is_express INTEGER DEFAULT 0",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for ddl in _ADDED_COLUMNS:
            conn.execute(text(ddl))
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="HangRail", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
