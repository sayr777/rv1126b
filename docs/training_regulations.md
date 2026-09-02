# Регламент обучения и дообучения моделей

## 1. Общие положения

Настоящий регламент определяет порядок первичного обучения, дообучения и валидации
моделей машинного зрения системы видеоаналитики на базе RV1126B.

Ответственный за выполнение регламента — инженер по машинному обучению (ML-инженер).
Все результаты обучения фиксируются в журнале `training/runs/training_log.csv`.

---

## 2. Триггеры для дообучения

Дообучение инициируется при наступлении любого из условий:

| Условие                                                    | Срок запуска  |
|------------------------------------------------------------|---------------|
| Точность OCR номеров < 94 % по итогам недельного аудита   | В течение 3 дней  |
| F1 детекции ремня или телефона < 0.85                      | В течение 3 дней  |
| Смена сезона (переход зима ↔ лето)                         | За 2 недели до     |
| Накоплено ≥ 1 000 новых размеченных кадров                 | Плановое, раз в месяц |
| Добавление новой камеры или точки установки                | До ввода в эксплуатацию |
| Жалобы оператора на ложные срабатывания > 5 % за неделю   | В течение 5 дней  |

---

## 3. Сбор данных

### 3.1 Захват кадров с устройства

```bash
# Кадры с фронтальной камеры (LPR, вафельная зона)
python training/collect_frames.py rtsp \
    --url rtsp://<device_ip>:8554/front \
    --out training/datasets/raw/front_<YYYYMMDD>/ \
    --interval 2.0 \
    --limit 1000

# Кадры с кабинной камеры (ремень, телефон)
python training/collect_frames.py rtsp \
    --url rtsp://<device_ip>:8554/cabin \
    --out training/datasets/raw/cabin_<YYYYMMDD>/ \
    --interval 2.0 \
    --limit 1000

# Копирование накопленных снимков нарушений
python training/collect_frames.py ssh \
    --host <device_ip> --user root \
    --remote /opt/traffic_ai/snapshots/ \
    --out training/datasets/raw/snapshots_<YYYYMMDD>/
```

### 3.2 Требования к составу датасета

| Условие съёмки        | Доля в датасете |
|-----------------------|-----------------|
| Дневное освещение     | ≥ 40 %          |
| Сумерки / пасмурно    | ≥ 20 %          |
| Ночь с IR подсветкой  | ≥ 20 %          |
| Дождь / снег          | ≥ 10 %          |
| Разные ракурсы авто   | ≥ 10 %          |

### 3.3 Разметка

Инструмент: **CVAT** (https://cvat.ai) или **Label Studio**.

| Модель            | Тип разметки      | Формат экспорта |
|-------------------|-------------------|-----------------|
| vehicle_yolov8n   | Bounding box      | YOLO TXT        |
| plate_yolov8n     | Bounding box      | YOLO TXT        |
| lprnet            | Имя файла = текст номера | Структура папок |
| seatbelt_mbv2     | Классификация     | Структура папок |
| phone_yolov8n     | Bounding box      | YOLO TXT        |

Минимальные объёмы для запуска обучения:

| Модель            | Train        | Val         |
|-------------------|--------------|-------------|
| vehicle_yolov8n   | 1 500 кадров | 300 кадров  |
| plate_yolov8n     | 2 000 кадров | 400 кадров  |
| lprnet            | NOMEROFF-NET (~50k) + 500 своих | 200 своих |
| seatbelt_mbv2     | 1 500 / класс | 300 / класс |
| phone_yolov8n     | 500 кадров   | 100 кадров  |

---

## 4. Аугментация

Выполняется перед обучением. Коэффициент × 5 для малых датасетов (< 2 000 кадров).

```bash
# Детекционные модели
python training/augment.py \
    --src training/datasets/raw/front_<YYYYMMDD>/ \
    --dst training/datasets/augmented/front_<YYYYMMDD>/ \
    --mode detection \
    --factor 5

# Классификационные модели (ремень)
python training/augment.py \
    --src training/datasets/raw/cabin_<YYYYMMDD>/ \
    --dst training/datasets/augmented/cabin_<YYYYMMDD>/ \
    --mode classification \
    --factor 5
```

---

## 5. Обучение моделей

### 5.1 Детектор автомобилей (YOLOv8n)

```bash
python training/lpr/train_vehicle.py \
    --data   training/datasets/vehicle/data.yaml \
    --epochs 50 \
    --batch  16 \
    --device 0
```

Целевая метрика: **mAP50 ≥ 0.88** на val-выборке.

### 5.2 Детектор номерного знака (YOLOv8n, 1 класс)

```bash
python training/lpr/train_plate.py \
    --data   training/datasets/plate/data.yaml \
    --epochs 80 \
    --imgsz  320 \
    --batch  32 \
    --device 0
```

Целевая метрика: **mAP50 ≥ 0.92**.

### 5.3 OCR номера (LPRNet, кириллица)

```bash
python training/lpr/train_lprnet.py \
    --dataset training/datasets/lprnet/ \
    --epochs  100 \
    --batch   64 \
    --device  cuda
```

Целевая метрика: **sequence accuracy ≥ 96 %** на val-выборке.

### 5.4 Классификатор ремня (MobileNetV2)

```bash
python training/cabin/train_seatbelt.py \
    --dataset training/datasets/seatbelt/ \
    --epochs  30 \
    --batch   32 \
    --device  0
```

Целевые метрики: **accuracy ≥ 93 %, F1(belt_off) ≥ 0.90**.

### 5.5 Детектор телефона (YOLOv8n finetune)

```bash
python training/cabin/finetune_phone.py \
    --data   training/datasets/phone/data.yaml \
    --epochs 40 \
    --batch  16 \
    --device 0
```

Целевая метрика: **mAP50 ≥ 0.80**.

---

## 6. Конвертация в RKNN INT8

После достижения целевых метрик:

```bash
# 1. Экспорт YOLOv8 в ONNX
yolo export model=runs/<task>/weights/best.pt format=onnx imgsz=640

# 2. Конвертация в RKNN
python models/convert/convert_onnx_to_rknn.py \
    --model  runs/<task>/weights/best.onnx \
    --output models/<name>.rknn \
    --calib  training/datasets/calibration/ \
    --target rk1126b
```

Проверить потерю точности при квантизации: допустимо снижение mAP50 не более **–2 %**.

---

## 7. Валидация на устройстве

```bash
# Скопировать новые модели на устройство
scp models/*.rknn root@<device_ip>:/opt/traffic_ai/models/

# Перезапустить firmware
ssh root@<device_ip> "systemctl restart traffic_ai"

# Запустить end-to-end оценку
python training/eval/eval_pipeline.py \
    --frames training/datasets/eval_frames/ \
    --gt     training/datasets/eval_gt.json \
    --host   <device_ip> \
    --report runs/eval/report_<YYYYMMDD>.json
```

### Критерии приёмки (gate для деплоя в продакшн)

| Метрика                            | Минимальное значение |
|------------------------------------|----------------------|
| LPR accuracy (sequence)            | ≥ 95 %              |
| Seatbelt F1 (belt_off)             | ≥ 0.88              |
| Phone precision                    | ≥ 0.80              |
| Waffle violation precision         | ≥ 0.90              |
| Waffle violation recall            | ≥ 0.85              |
| FPS фронтального потока            | ≥ 22                |

Если хотя бы одна метрика не пройдена — деплой **заблокирован**, ML-инженер
анализирует причину и повторяет цикл с шага 3.

---

## 8. Деплой новых моделей

1. Зафиксировать версию моделей в `models/README.md` (хэш файла, дата, метрики).
2. Скопировать `.rknn` файлы на все устройства группы.
3. Перезапустить `traffic_ai` через `systemctl`.
4. Наблюдать за метриками в Grafana в течение 48 часов.
5. При деградации — откатить предыдущую версию моделей.

---

## 9. Журнал обучения

Каждый цикл обучения фиксируется в `training/runs/training_log.csv`:

| Поле          | Описание                              |
|---------------|---------------------------------------|
| date          | Дата обучения                         |
| model         | Название модели                       |
| dataset_size  | Число кадров train / val              |
| epochs        | Количество эпох                       |
| metric_name   | Целевая метрика                       |
| metric_val    | Достигнутое значение                  |
| rknn_drop     | Снижение метрики после квантизации    |
| deployed      | Да / Нет                              |
| notes         | Примечания                            |
