from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    PLATE_READ        = "PLATE_READ"
    WAFFLE_VIOLATION  = "WAFFLE_VIOLATION"
    NO_SEATBELT       = "NO_SEATBELT"
    PHONE_IN_HAND     = "PHONE_IN_HAND"


# ---------- Входящие события от устройства ----------

class EventIn(BaseModel):
    type:       EventType
    plate:      Optional[str]  = None
    track_id:   Optional[int]  = None
    zone:       Optional[str]  = None
    dwell_sec:  Optional[float]= None
    conf:       float          = Field(ge=0.0, le=1.0)
    timestamp:  datetime
    cam_id:     str
    snapshot:   Optional[str]  = None


# ---------- Ответы API ----------

class EventOut(BaseModel):
    id:            int
    camera_id:     str
    event_type:    EventType
    plate:         Optional[str]
    track_id:      Optional[int]
    zone_name:     Optional[str]
    dwell_sec:     Optional[float]
    confidence:    float
    snapshot_url:  Optional[str]
    occurred_at:   datetime

    model_config = {"from_attributes": True}


class EventList(BaseModel):
    total: int
    items: List[EventOut]


class CameraStatus(BaseModel):
    id:          str
    location:    str
    lat:         Optional[float]
    lon:         Optional[float]
    is_active:   bool
    last_seen:   Optional[datetime]


class DailyStat(BaseModel):
    camera_id:  str
    event_type: EventType
    day:        str          # "2026-09-03"
    total:      int
    avg_conf:   float


class Violator(BaseModel):
    plate:            str
    violation_count:  int
    last_seen:        datetime
    violation_types:  List[str]


class ZoneUpdate(BaseModel):
    name:    str
    polygon: List[List[float]]   # [[x, y], ...]


class Heartbeat(BaseModel):
    cam_id:    str
    fps:       float
    cpu_temp:  float
    npu_load:  float
    uptime_s:  int
