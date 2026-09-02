from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import Event, Camera, get_db
from api.schemas import EventIn, EventOut, EventList

router = APIRouter(prefix="/api/events", tags=["events"])

SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "snapshots")


@router.post("", status_code=201)
async def receive_event(payload: EventIn, db: AsyncSession = Depends(get_db)):
    """Принимает событие от устройства. Вызывается прошивкой через HTTP POST."""
    event = Event(
        camera_id    = payload.cam_id,
        event_type   = payload.type.value,
        plate        = payload.plate,
        track_id     = payload.track_id,
        zone_name    = payload.zone,
        dwell_sec    = payload.dwell_sec,
        confidence   = payload.conf,
        snapshot_path= payload.snapshot,
        occurred_at  = payload.timestamp,
    )
    db.add(event)

    # Обновляем last_seen камеры
    cam = await db.get(Camera, payload.cam_id)
    if cam:
        cam.last_seen = datetime.utcnow()
    else:
        db.add(Camera(id=payload.cam_id, location="unknown", last_seen=datetime.utcnow()))

    await db.commit()
    return {"id": event.id}


@router.get("", response_model=EventList)
async def list_events(
    type:     Optional[str]      = Query(None),
    plate:    Optional[str]      = Query(None),
    camera:   Optional[str]      = Query(None),
    from_dt:  Optional[datetime] = Query(None, alias="from"),
    to_dt:    Optional[datetime] = Query(None, alias="to"),
    limit:    int                = Query(50, le=500),
    offset:   int                = Query(0),
    db:       AsyncSession       = Depends(get_db),
):
    q = select(Event)
    if type:    q = q.where(Event.event_type == type)
    if plate:   q = q.where(Event.plate.ilike(f"%{plate}%"))
    if camera:  q = q.where(Event.camera_id == camera)
    if from_dt: q = q.where(Event.occurred_at >= from_dt)
    if to_dt:   q = q.where(Event.occurred_at <= to_dt)

    total_q = select(func.count()).select_from(q.subquery())
    total   = (await db.execute(total_q)).scalar_one()

    rows = (await db.execute(
        q.order_by(Event.occurred_at.desc()).limit(limit).offset(offset)
    )).scalars().all()

    items = [
        EventOut(
            id           = r.id,
            camera_id    = r.camera_id,
            event_type   = r.event_type,
            plate        = r.plate,
            track_id     = r.track_id,
            zone_name    = r.zone_name,
            dwell_sec    = r.dwell_sec,
            confidence   = r.confidence,
            snapshot_url = f"/api/events/{r.id}/snapshot" if r.snapshot_path else None,
            occurred_at  = r.occurred_at,
        )
        for r in rows
    ]
    return EventList(total=total, items=items)


@router.get("/{event_id}/snapshot")
async def get_snapshot(event_id: int, db: AsyncSession = Depends(get_db)):
    event = await db.get(Event, event_id)
    if not event or not event.snapshot_path:
        raise HTTPException(404, "Snapshot not found")
    path = event.snapshot_path
    if not os.path.isabs(path):
        path = os.path.join(SNAPSHOT_DIR, path)
    if not os.path.exists(path):
        raise HTTPException(404, "Snapshot file missing on disk")
    return FileResponse(path, media_type="image/jpeg")
