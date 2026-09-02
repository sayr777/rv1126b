-- Traffic AI — схема базы данных
-- PostgreSQL 16

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- для поиска по номеру

-- Камеры
CREATE TABLE cameras (
    id          VARCHAR(32) PRIMARY KEY,            -- "cam01"
    location    TEXT        NOT NULL,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    installed_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen   TIMESTAMPTZ,
    is_active   BOOLEAN     DEFAULT TRUE
);

-- Зоны вафельной разметки (для каждой камеры)
CREATE TABLE zones (
    id          SERIAL      PRIMARY KEY,
    camera_id   VARCHAR(32) REFERENCES cameras(id) ON DELETE CASCADE,
    name        VARCHAR(64) NOT NULL,
    polygon     JSONB       NOT NULL,               -- [[x,y], ...]
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Все события нарушений
CREATE TABLE events (
    id              BIGSERIAL   PRIMARY KEY,
    camera_id       VARCHAR(32) REFERENCES cameras(id),
    event_type      VARCHAR(32) NOT NULL,           -- PLATE_READ | WAFFLE_VIOLATION | NO_SEATBELT | PHONE_IN_HAND
    plate           VARCHAR(16),
    track_id        INTEGER,
    zone_name       VARCHAR(64),
    dwell_sec       REAL,
    confidence      REAL,
    snapshot_path   TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_events_occurred ON events (occurred_at DESC);
CREATE INDEX idx_events_type     ON events (event_type);
CREATE INDEX idx_events_plate    ON events USING GIN (plate gin_trgm_ops);
CREATE INDEX idx_events_camera   ON events (camera_id, occurred_at DESC);

-- Агрегат нарушений по суткам (мат. представление, обновляется каждые 5 мин)
CREATE MATERIALIZED VIEW daily_stats AS
SELECT
    camera_id,
    event_type,
    DATE(occurred_at AT TIME ZONE 'Europe/Moscow') AS day,
    COUNT(*)                                        AS total,
    AVG(confidence)                                 AS avg_conf
FROM events
GROUP BY camera_id, event_type, day
WITH DATA;

CREATE UNIQUE INDEX ON daily_stats (camera_id, event_type, day);

-- Функция обновления мат. представления
CREATE OR REPLACE FUNCTION refresh_daily_stats()
RETURNS void LANGUAGE sql AS $$
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_stats;
$$;

-- Топ нарушителей по номеру (за последние 30 дней)
CREATE VIEW top_violators AS
SELECT
    plate,
    COUNT(*)          AS violation_count,
    MAX(occurred_at)  AS last_seen,
    array_agg(DISTINCT event_type) AS violation_types
FROM events
WHERE plate IS NOT NULL
  AND occurred_at > NOW() - INTERVAL '30 days'
GROUP BY plate
ORDER BY violation_count DESC;
