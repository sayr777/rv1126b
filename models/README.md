# Модели

Папка `models/` содержит `.rknn` файлы моделей (не хранятся в git — см. `.gitignore`).
Скрипты конвертации находятся в `models/convert/`.

## Используемые модели

| Файл                      | Задача                    | Архитектура     | Вход      | Время NPU |
|---------------------------|---------------------------|-----------------|-----------|-----------|
| vehicle_yolov8n.rknn      | Детекция автомобилей      | YOLOv8n         | 640×640   | ~15 мс    |
| plate_yolov8n.rknn        | Детекция номерного знака  | YOLOv8n (1 cls) | 320×192   | ~8 мс     |
| lprnet_crnn.rknn          | OCR номера (кириллица)    | LPRNet          | 94×24     | ~4 мс     |
| seatbelt_mbv2.rknn        | Ремень безопасности       | MobileNetV2     | 224×224   | ~3 мс     |
| phone_yolov8n.rknn        | Телефон в руках           | YOLOv8n (COCO)  | 640×640   | ~15 мс    |

**Суммарная нагрузка:** ~45 мс при последовательном запуске.
NPU (3 TOPS) обрабатывает несколько моделей за время одного кадра (40 мс при 25 fps).

---

## LPR Pipeline — источники моделей

### 1. vehicle_yolov8n.rknn — детекция автомобилей

**Источник базовой модели:** RKNN Model Zoo
```
git clone https://github.com/airockchip/rknn_model_zoo
# Готовая модель:
rknn_model_zoo/models/CV/object_detection/yolo/yolov8/model/yolov8n.rknn
```

**Или экспорт через Ultralytics:**
```bash
pip install ultralytics
yolo export model=yolov8n.pt format=rknn name=rk1126b
```

**Классы из COCO:** car(2), bus(5), truck(7) — фильтруются в коде.
Для улучшения точности на российских авто — дообучение (см. `training/lpr/`).

---

### 2. plate_yolov8n.rknn — детекция номерного знака

**Датасеты для обучения:**
- CCPD2020 (китайские номера, структура похожа)
- Собственный сбор с устройства через `training/collect_frames.py`

**Обучение:** `training/lpr/train_plate.py`

---

### 3. lprnet_crnn.rknn — OCR номера (кириллица)

**Источник:** RKNN Model Zoo — `models/CV/ocr/lprnet/`

**Важно:** Базовая модель обучена на латинице и цифрах.
Для кириллических номеров РФ необходимо дообучение:
```
Датасет: NOMEROFF-NET (https://github.com/ria-com/nomeroff-net)
         — содержит номера RU, BY, KZ, UA с кириллицей
```
**Дообучение:** `training/lpr/train_lprnet.py`

---

### 4. seatbelt_mbv2.rknn — ремень безопасности

**Базовая модель:** MobileNetV2 (ImageNet pretrained)
**Дообучение (2 класса):** belt_on / belt_off
**Датасет:** ручная разметка кадров с кабинной камеры (~2 000 изображений).
**Обучение:** `training/cabin/train_seatbelt.py`

---

### 5. phone_yolov8n.rknn — телефон в руках

**Источник:** та же модель что и `vehicle_yolov8n.rknn` (YOLOv8n COCO).
Класс 67 = `cell phone` уже есть в COCO.
Для повышения точности в условиях кабины — finetune: `training/cabin/finetune_phone.py`.

---

## Получение и конвертация моделей

```bash
# 1. Установить RKNN-Toolkit2 (на ПК разработчика, не на устройстве)
pip install rknn-toolkit2

# 2. Конвертировать ONNX в RKNN INT8
python models/convert/convert_onnx_to_rknn.py \
    --model  /path/to/yolov8n.onnx \
    --output models/vehicle_yolov8n.rknn \
    --calib  training/datasets/calibration/ \
    --target rk1126b

# 3. Скопировать .rknn на устройство
scp models/vehicle_yolov8n.rknn root@10.0.0.5:/opt/traffic_ai/models/
```
