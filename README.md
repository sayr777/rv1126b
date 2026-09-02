# RV1126B — Traffic Enforcement AI Camera

Система видеоаналитики нарушений ПДД на перекрёстках на базе Rockchip RV1126B.
Весь инференс выполняется на борту устройства — сервер нужен только для хранения событий и веб-интерфейса.

## Функции

| Функция               | Нарушение                             | Статья КоАП РФ |
|-----------------------|---------------------------------------|----------------|
| LPR                   | Идентификация ТС по номерному знаку   | —              |
| Вафельная разметка    | Остановка на жёлтой сетке            | 12.13 ч.1      |
| Ремень безопасности   | Водитель без ремня                    | 12.6           |
| Телефон в руках       | Использование телефона за рулём       | 12.36.1        |

## Железо

| Компонент               | Характеристики                                   |
|-------------------------|--------------------------------------------------|
| SoC                     | Rockchip RV1126B — 4× Cortex-A53 @ 1.6 GHz      |
| NPU                     | 3 TOPS INT8 (RKNPU2) — YOLOv8n ~15 мс           |
| ISP                     | 12MP AI-ISP, 2× MIPI CSI-2 одновременно         |
| Камера фронтальная      | Sony IMX335 5MP — LPR + вафельная зона           |
| Камера кабинная         | OV4689 StarLight 4MP — ремень + телефон          |
| IR подсветка            | 850 нм, 30 Вт (ночной режим)                     |
| Рекомендованный SoM     | Luckfox Aura (1 GB LPDDR4, 16 GB eMMC) ~$45     |
| Себестоимость устройства| ~$159 (1 шт.), ~$120 (50+ шт.)                  |

## Структура репозитория

```
rv1126b/
├── docs/
│   ├── architecture.md    архитектура, схема установки
│   ├── algorithm.md       пошаговый алгоритм конвейера
│   └── api.md             HTTP / MQTT / RTSP / REST протоколы
├── hardware/
│   ├── bom.md             Bill of Materials
│   ├── wiring.md          схема подключения, распиновка
│   └── datasheets.md      даташиты и справочные материалы
├── firmware/
│   ├── src/               C++17, Linux, RKNN runtime
│   │   ├── lpr/           LPR pipeline (vehicle det → plate det → OCR)
│   │   ├── waffle/        ByteTrack + Zone + ViolationDetector
│   │   ├── cabin/         SeatbeltDetector + PhoneDetector
│   │   ├── rknn/          обёртка RKNN API + пул контекстов
│   │   ├── camera/        V4L2 mmap захват кадров
│   │   └── output/        EventPublisher (HTTP + MQTT + JPEG)
│   ├── config/
│   │   ├── config.json    пути моделей, камеры, адрес сервера
│   │   └── zones.json     полигоны вафельной разметки
│   └── tests/
├── models/
│   ├── README.md          описание моделей, источники, команды
│   └── convert/
│       └── convert_onnx_to_rknn.py   ONNX → RKNN INT8
├── training/
│   ├── collect_frames.py  сбор кадров с устройства (RTSP / SSH)
│   ├── augment.py         аугментация датасета
│   ├── lpr/
│   │   ├── train_vehicle.py    дообучение YOLOv8n на авто РФ
│   │   ├── train_plate.py      обучение детектора номеров
│   │   └── train_lprnet.py     дообучение LPRNet на кириллицу
│   ├── cabin/
│   │   ├── train_seatbelt.py   MobileNetV2 ремень безопасности
│   │   └── finetune_phone.py   дообучение YOLOv8n на телефон
│   └── eval/
│       └── eval_pipeline.py    end-to-end оценка конвейера
└── server/
    ├── docker-compose.yml  API + PostgreSQL + MQTT + Grafana
    ├── .env                переменные окружения (не в git)
    ├── api/                FastAPI, SQLAlchemy, Pydantic
    ├── db/schema.sql       схема БД, материализованные представления
    └── mqtt/               MQTT subscriber + mosquitto.conf
```

## Модели (NPU INT8, RKNN)

| Файл                   | Задача                  | Архитектура     | Вход    | Время  |
|------------------------|-------------------------|-----------------|---------|--------|
| vehicle_yolov8n.rknn   | Детекция автомобилей    | YOLOv8n         | 640×640 | ~15 мс |
| plate_yolov8n.rknn     | Детекция номерного знака| YOLOv8n         | 320×192 | ~8 мс  |
| lprnet_crnn.rknn       | OCR номера (кириллица)  | LPRNet          | 94×24   | ~4 мс  |
| seatbelt_mbv2.rknn     | Ремень безопасности     | MobileNetV2     | 224×224 | ~3 мс  |
| phone_yolov8n.rknn     | Телефон в руках         | YOLOv8n (COCO)  | 640×640 | ~15 мс |

Инструкция по получению и конвертации — [`models/README.md`](models/README.md).

## Быстрый старт

### 1. Сборка firmware на устройстве

```bash
# Установить RKNN runtime на RV1126B (один раз)
scp librknnrt.so root@device:/usr/lib/

# Сборка
mkdir firmware/build && cd firmware/build
cmake .. -DRKNN_SDK_ROOT=/path/to/rknn-toolkit2
make -j4

# Запуск
./traffic_ai ../config/config.json
```

### 2. Конвертация модели (на ПК разработчика)

```bash
pip install rknn-toolkit2 ultralytics

# Экспорт YOLOv8n в ONNX
yolo export model=yolov8n.pt format=onnx imgsz=640

# Конвертация в RKNN INT8
python models/convert/convert_onnx_to_rknn.py \
    --model  yolov8n.onnx \
    --output models/vehicle_yolov8n.rknn \
    --calib  training/datasets/calibration/ \
    --target rk1126b
```

### 3. Запуск сервера

```bash
cd server
cp .env.example .env    # заполнить переменные
docker compose up -d

# API: http://localhost:8080
# Grafana: http://localhost:3000  (admin / admin)
```

### 4. Обучение моделей

```bash
pip install ultralytics torch torchvision albumentations nomeroff-net

# Сбор кадров с устройства
python training/collect_frames.py rtsp \
    --url rtsp://10.0.0.5:8554/front --out training/datasets/raw/ --limit 500

# Аугментация
python training/augment.py \
    --src training/datasets/raw/ --dst training/datasets/augmented/ --factor 5

# Дообучение детектора авто
python training/lpr/train_vehicle.py --epochs 50 --batch 16 --device 0

# Обучение классификатора ремня
python training/cabin/train_seatbelt.py --epochs 30 --batch 32

# End-to-end оценка
python training/eval/eval_pipeline.py \
    --frames training/datasets/eval/ --gt eval_gt.json
```

## Архитектура конвейера

```
/dev/video0 (фронт) ──► ByteTrack ──► ViolationDetector (вафельная зона)
                    └──► LPRPipeline  ──► plate OCR ──► EventPublisher
                                                              │
/dev/video1 (кабина)──► SeatbeltDetector ───────────────────►│──► HTTP POST
                    └──► PhoneDetector ──────────────────────►│──► MQTT
                                                              │──► JPEG снимок
```

Подробнее: [`docs/architecture.md`](docs/architecture.md), [`docs/algorithm.md`](docs/algorithm.md).

## Взаимодействие с сервером

Устройство отправляет события по HTTP POST и MQTT. Пример события:

```json
{
  "type": "WAFFLE_VIOLATION",
  "plate": "А123БВ77",
  "zone": "waffle_main",
  "dwell_sec": 4.2,
  "conf": 0.91,
  "timestamp": "2026-09-03T10:15:33Z",
  "cam_id": "cam01"
}
```

REST API сервера: [`docs/api.md`](docs/api.md).

## Лицензия

MIT
