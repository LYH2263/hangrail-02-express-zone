from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# 旧版本数据库（create_all 不会给已存在的表补列）的幂等迁移：
# 专区列缺省 NULL = 未划专区 = 全杆可挂；is_express 缺省 0 = 普通工单。
def ensure_columns() -> None:
    if engine.dialect.name != "postgresql":
        return
    statements = [
        "ALTER TABLE hang_rails ADD COLUMN IF NOT EXISTS express_zone_start_cm DOUBLE PRECISION",
        "ALTER TABLE hang_rails ADD COLUMN IF NOT EXISTS express_zone_end_cm DOUBLE PRECISION",
        "ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS is_express INTEGER DEFAULT 0",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
