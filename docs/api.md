# Взаимодействие с сервисом

## Протоколы

| Протокол | Назначение                             | Направление        |
|----------|----------------------------------------|--------------------|
| HTTP POST | Отправка событий нарушений            | устройство → сервер |
| MQTT      | Быстрые нотификации + heartbeat       | устройство → брокер |
| RTSP      | Живое видео с overlay                 | устройство → VMS   |
| REST API  | Управление устройством, запрос истории | сервер → устройство |

---

## HTTP POST — событие нарушения

**Endpoint:** `POST /event`

```http
POST /event HTTP/1.1
Host: 10.0.0.1:8080
Content-Type: application/json

{
  "type":       "WAFFLE_VIOLATION",
  "plate":      "А123БВ77",
  "track_id":   42,
  "zone":       "waffle_main",
  "dwell_sec":  4.2,
  "conf":       0.91,
  "timestamp":  "2026-09-03T10:15:33Z",
  "cam_id":     "cam01",
  "snapshot":   "http://10.0.0.5/snapshots/20260903_101533_42.jpg"
}
```

**Типы событий:**

| type              | Описание                        | Доп. поля                 |
|-------------------|---------------------------------|---------------------------|
| PLATE_READ        | Номер успешно считан            | plate, conf               |
| WAFFLE_VIOLATION  | Остановка на вафельной разметке | plate, zone, dwell_sec    |
| NO_SEATBELT       | Водитель без ремня              | conf                      |
| PHONE_IN_HAND     | Телефон в руках водителя        | conf                      |

---

## MQTT

```
Топик:   traffic/{cam_id}/event      QoS 1
Payload: тот же JSON, что и HTTP POST

Топик:   traffic/{cam_id}/heartbeat  QoS 0  (каждые 30 с)
Payload: { "fps": 24.8, "cpu_temp": 61, "npu_load": 72, "uptime_s": 3600 }
```

---

## RTSP

| Поток   | URL                                | Описание               |
|---------|------------------------------------|------------------------|
| front   | `rtsp://10.0.0.5:8554/front`       | Фронт с bbox overlay   |
| cabin   | `rtsp://10.0.0.5:8554/cabin`       | Кабина с маркерами     |

Стек: `mediamtx` (go2rtc) — запускается на борту RV1126B.

---

## REST API сервера

| Метод  | Путь                              | Описание                            |
|--------|-----------------------------------|-------------------------------------|
| GET    | `/api/events`                     | История событий (фильтр: type, plate, from, to) |
| GET    | `/api/events/{id}/snapshot`       | Скачать JPEG снимка                 |
| GET    | `/api/cameras`                    | Список камер и статус               |
| POST   | `/api/cameras/{id}/zones`         | Обновить полигон вафельной зоны     |
| GET    | `/api/stats/daily`                | Сводка нарушений за сутки           |
| GET    | `/api/stats/plates`               | Рейтинг нарушителей по номеру       |

### Пример ответа GET /api/events

```json
{
  "total": 142,
  "items": [
    {
      "id": 1001,
      "type": "NO_SEATBELT",
      "plate": "В456ГД77",
      "conf": 0.88,
      "timestamp": "2026-09-03T10:15:33Z",
      "snapshot_url": "/api/events/1001/snapshot"
    }
  ]
}
```
