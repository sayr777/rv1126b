import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, BigInteger
from datetime import datetime


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://traffic:traffic@localhost:5432/traffic"
)

engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Camera(Base):
    __tablename__ = "cameras"

    id:           Mapped[str]            = mapped_column(String(32), primary_key=True)
    location:     Mapped[str]            = mapped_column(Text)
    lat:          Mapped[float | None]   = mapped_column(Float, nullable=True)
    lon:          Mapped[float | None]   = mapped_column(Float, nullable=True)
    is_active:    Mapped[bool]           = mapped_column(Boolean, default=True)
    last_seen:    Mapped[datetime | None]= mapped_column(DateTime(timezone=True), nullable=True)


class Event(Base):
    __tablename__ = "events"

    id:             Mapped[int]           = mapped_column(BigInteger, primary_key=True)
    camera_id:      Mapped[str]           = mapped_column(String(32))
    event_type:     Mapped[str]           = mapped_column(String(32))
    plate:          Mapped[str | None]    = mapped_column(String(16), nullable=True)
    track_id:       Mapped[int | None]    = mapped_column(Integer, nullable=True)
    zone_name:      Mapped[str | None]    = mapped_column(String(64), nullable=True)
    dwell_sec:      Mapped[float | None]  = mapped_column(Float, nullable=True)
    confidence:     Mapped[float]         = mapped_column(Float)
    snapshot_path:  Mapped[str | None]    = mapped_column(Text, nullable=True)
    occurred_at:    Mapped[datetime]      = mapped_column(DateTime(timezone=True))


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
