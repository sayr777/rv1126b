#!/usr/bin/env python3
"""
MQTT subscriber — слушает события от камер и сохраняет в PostgreSQL.

Дублирует HTTP POST на случай потери пакетов:
  - HTTP POST — основной канал (гарантирован)
  - MQTT      — быстрые нотификации + heartbeat

Topics:
    traffic/{cam_id}/event      — TrafficEvent JSON
    traffic/{cam_id}/heartbeat  — {"fps":..., "cpu_temp":..., ...}
"""

import json
import logging
import os
import signal
import sys
from datetime import datetime

import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mqtt_sub")

MQTT_HOST          = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT          = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX  = os.getenv("MQTT_TOPIC_PREFIX", "traffic/#")
DATABASE_URL       = os.getenv("DATABASE_URL",
                                "postgresql://traffic:traffic@localhost:5432/traffic")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def save_event(conn, payload: dict):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO events
              (camera_id, event_type, plate, track_id, zone_name,
               dwell_sec, confidence, snapshot_path, occurred_at)
            VALUES
              (%(cam_id)s, %(type)s, %(plate)s, %(track_id)s, %(zone)s,
               %(dwell_sec)s, %(conf)s, %(snapshot)s, %(timestamp)s)
            ON CONFLICT DO NOTHING
        """, {
            "cam_id":    payload.get("cam_id"),
            "type":      payload.get("type"),
            "plate":     payload.get("plate"),
            "track_id":  payload.get("track_id"),
            "zone":      payload.get("zone"),
            "dwell_sec": payload.get("dwell_sec"),
            "conf":      payload.get("conf", 0),
            "snapshot":  payload.get("snapshot"),
            "timestamp": payload.get("timestamp"),
        })
        conn.commit()


def update_heartbeat(conn, cam_id: str):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE cameras SET last_seen = NOW() WHERE id = %s
        """, (cam_id,))
        conn.commit()


def on_connect(client, userdata, flags, rc, properties=None):
    log.info(f"Connected to MQTT broker (rc={rc})")
    client.subscribe(MQTT_TOPIC_PREFIX)


def on_message(client, userdata, msg):
    conn = userdata["conn"]
    topic_parts = msg.topic.split("/")   # traffic / cam01 / event|heartbeat

    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        log.warning(f"Invalid JSON on {msg.topic}")
        return

    if len(topic_parts) < 3:
        return

    cam_id    = topic_parts[1]
    msg_type  = topic_parts[2]

    if msg_type == "event":
        payload["cam_id"] = cam_id
        try:
            save_event(conn, payload)
            log.info(f"Event saved: {cam_id} / {payload.get('type')}")
        except Exception as e:
            log.error(f"DB error: {e}")
            conn.rollback()

    elif msg_type == "heartbeat":
        try:
            update_heartbeat(conn, cam_id)
        except Exception as e:
            log.error(f"Heartbeat DB error: {e}")
            conn.rollback()


def main():
    conn = get_conn()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.user_data_set({"conn": conn})
    client.on_connect = on_connect
    client.on_message = on_message

    def shutdown(sig, frame):
        log.info("Shutting down...")
        client.disconnect()
        conn.close()
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    log.info(f"Subscribing to {MQTT_TOPIC_PREFIX} on {MQTT_HOST}:{MQTT_PORT}")
    client.loop_forever()


if __name__ == "__main__":
    main()
