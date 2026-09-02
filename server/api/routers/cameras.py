from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import Camera, zones as ZoneTable, get_db
from api.schemas import CameraStatus, ZoneUpdate, Heartbeat

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraStatus])
async def list_cameras(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Camera).order_by(Camera.id))).scalars().all()
    return [
        CameraStatus(
            id=c.id, location=c.location, lat=c.lat, lon=c.lon,
            is_active=c.is_active, last_seen=c.last_seen,
        )
        for c in rows
    ]


@router.post("/{cam_id}/zones", status_code=204)
async def update_zone(
    cam_id: str,
    payload: ZoneUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Обновляет или создаёт зону вафельной разметки для камеры."""
    from api.database import Zone as ZoneModel
    cam = await db.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, f"Camera {cam_id} not found")

    existing = (await db.execute(
        select(ZoneModel).where(ZoneModel.camera_id == cam_id,
                                ZoneModel.name == payload.name)
    )).scalar_one_or_none()

    if existing:
        existing.polygon = payload.polygon
    else:
        db.add(ZoneModel(camera_id=cam_id, name=payload.name, polygon=payload.polygon))

    await db.commit()


@router.post("/{cam_id}/heartbeat", status_code=204)
async def heartbeat(
    cam_id: str,
    payload: Heartbeat,
    db: AsyncSession = Depends(get_db),
):
    """Принимает heartbeat от прошивки; обновляет last_seen."""
    from datetime import datetime
    cam = await db.get(Camera, cam_id)
    if cam:
        cam.last_seen = datetime.utcnow()
        await db.commit()
