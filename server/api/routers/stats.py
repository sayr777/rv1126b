from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas import DailyStat, Violator

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/daily", response_model=list[DailyStat])
async def daily_stats(
    camera: str | None = Query(None),
    days:   int        = Query(7, le=90),
    db:     AsyncSession = Depends(get_db),
):
    """Сводка нарушений по суткам из материализованного представления."""
    where = "WHERE day >= CURRENT_DATE - :days"
    params: dict = {"days": days}
    if camera:
        where += " AND camera_id = :camera"
        params["camera"] = camera

    rows = (await db.execute(
        text(f"SELECT camera_id, event_type, day::text, total, avg_conf "
             f"FROM daily_stats {where} ORDER BY day DESC, total DESC"),
        params,
    )).fetchall()

    return [
        DailyStat(camera_id=r[0], event_type=r[1], day=r[2],
                  total=r[3], avg_conf=round(r[4], 3))
        for r in rows
    ]


@router.get("/plates", response_model=list[Violator])
async def top_violators(
    limit: int = Query(20, le=100),
    db:    AsyncSession = Depends(get_db),
):
    """Топ нарушителей по номеру за последние 30 дней."""
    rows = (await db.execute(
        text("SELECT plate, violation_count, last_seen, violation_types "
             "FROM top_violators LIMIT :limit"),
        {"limit": limit},
    )).fetchall()

    return [
        Violator(plate=r[0], violation_count=r[1],
                 last_seen=r[2], violation_types=r[3])
        for r in rows
    ]


@router.post("/refresh", status_code=204)
async def refresh_stats(db: AsyncSession = Depends(get_db)):
    """Принудительно обновить материализованное представление daily_stats."""
    await db.execute(text("SELECT refresh_daily_stats()"))
    await db.commit()
