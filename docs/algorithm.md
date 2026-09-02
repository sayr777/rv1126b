# Алгоритм работы

## Модели и время инференса (NPU INT8)

| Задача | Модель | Вход | Время NPU |
|--------|--------|------|-----------|
| Детекция авто | YOLOv8n (COCO finetune) | 640×640 | ~15 мс |
| Детекция номера | YOLOv8n (1 cls, plate) | 320×192 | ~8 мс |
| OCR номера | LPRNet (кириллица) | 94×24 | ~4 мс |
| Ремень безопасности | MobileNetV2 INT8 | 224×224 | ~3 мс |
| Телефон в руках | YOLOv8n COCO cls=67 | 640×640 | ~15 мс |

---

## Поток 1 — фронтальная камера (25 fps, ~40 мс/кадр)

```
t=0ms   t=5ms   t=20ms  t=21ms  t=21.5ms  t=33ms   t=40ms
  │───────│───────│───────│────────│─────────│────────│
  V4L2    │  YOLOv8n      │  ByteTrack   LprPipeline  ▲
  grab    │  vehicle      │  +Zone       (каждые      следующий
  ~5ms    │  ~15ms(NPU)   │  ~1ms        5 кадров)    кадр
                          Zone check                  ~12ms(NPU)

Шаг 1 — CAPTURE
  Захватить кадр 1920×1080 BGR из /dev/video0 через V4L2 mmap.

Шаг 2 — DETECT VEHICLES
  Масштабировать → 640×640 → YOLOv8n NPU.
  Постобработка: NMS (IoU=0.45, conf=0.45).
  Фильтр классов: car(2), bus(5), truck(7).

Шаг 3 — TRACK
  ByteTrack.update(bboxes) → список Track{id, box, hits, age}.
  Треки с hits < 3 — предварительные (не используются для нарушений).

Шаг 4 — ZONE CHECK  (каждый кадр)
  Для каждого подтверждённого трека:
    zone.contains_center(bbox)?
      ДА:  track.enter_time уже записан?
              НЕТ → записать enter_time = now()
              ДА  → dwell = now() - enter_time
                    dwell > 3.0 с AND не фаял ранее → ViolationEvent(WAFFLE)
      НЕТ: сбросить enter_time трека

Шаг 5 — LPR  (каждые 5 кадров OR при появлении нового трека)
  Для каждого bbox авто:
    a. Crop авто из кадра → resize 320×192
    b. plate_det (YOLOv8n, NPU, ~8 мс) → plate_bbox
    c. Crop номера → resize 94×24
    d. LPRNet (NPU, ~4 мс) → CTC decode → "А123БВ77" + conf
    e. violation_detector.attach_plate(track_id, plate)

Шаг 6 — PUBLISH
  Новые события → EventPublisher:
    - JPEG снимок с overlay (bbox + номер + время)
    - HTTP POST JSON
    - MQTT publish
```

---

## Поток 2 — кабинная камера (25 fps)

```
Шаг 1 — CAPTURE
  Захватить кадр 1280×720 BGR из /dev/video1.

Шаг 2 — ROI
  Вырезать зону водителя: левая половина кадра (для правостороннего движения).

Шаг 3 — SEATBELT
  Crop ROI → resize 224×224 → MobileNetV2 (NPU, ~3 мс).
  Результат: {belt_on / belt_off, conf}.
  Если belt_off AND conf > 0.75 → SeatbeltResult → EventPublisher.

Шаг 4 — PHONE
  Полный ROI водителя → resize 640×640 → YOLOv8n (NPU, ~15 мс).
  Фильтр класс = 67 (cell phone).
  Если conf > 0.50 → PhoneEvent → EventPublisher.

Шаг 5 — PUBLISH
  Аналогично потоку 1.
```

---

## Фильтрация ложных срабатываний

| Ситуация | Метод фильтрации |
|---------|-----------------|
| Авто проезжает через зону (не стоит) | dwell < 3 с → не нарушение |
| Пешеход в зоне | Фильтр классов YOLOv8n (только авто) |
| Авто на зелёный | UART фаза светофора OR детекция зелёного (опционально) |
| Низкая уверенность OCR | conf < 0.70 → номер не публикуется |
| Ремень пассажира, не водителя | ROI ограничен зоной водителя |

---

## Событийная модель

```
TrafficEvent {
  type:       PLATE_READ | WAFFLE_VIOLATION | NO_SEATBELT | PHONE_IN_HAND
  plate:      "А123БВ77"   (пусто если не считан)
  track_id:   42
  zone:       "waffle_main"
  dwell_sec:  4.2
  conf:       0.91
  timestamp:  "2026-09-03T10:15:33Z"
  cam_id:     "cam01"
  jpeg_path:  "/snapshots/20260903_101533_42.jpg"
}
```
