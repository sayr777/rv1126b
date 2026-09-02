# Training — обучение и дообучение моделей

## Структура

```
training/
├── collect_frames.py      сбор кадров с устройства (RTSP / SSH)
├── augment.py             аугментация датасета
├── lpr/
│   ├── train_vehicle.py   дообучение YOLOv8n на авто РФ
│   ├── train_plate.py     обучение YOLOv8n на детекцию номеров
│   └── train_lprnet.py    дообучение LPRNet на кириллицу (NOMEROFF-NET)
├── cabin/
│   ├── train_seatbelt.py  обучение MobileNetV2 — ремень
│   └── finetune_phone.py  дообучение YOLOv8n — телефон в кабине
└── eval/
    └── eval_pipeline.py   end-to-end оценка всего конвейера
```

## Зависимости

```bash
pip install ultralytics torch torchvision rknn-toolkit2 \
            opencv-python albumentations nomeroff-net
```

## Пайплайн обучения — общая схема

```
1. Сбор данных
   collect_frames.py → datasets/raw/

2. Разметка
   CVAT / Roboflow / Label Studio

3. Аугментация
   augment.py → datasets/augmented/

4. Обучение
   train_*.py → runs/train/.../best.pt

5. Экспорт в ONNX
   yolo export model=best.pt format=onnx

6. Конвертация в RKNN INT8
   models/convert/convert_onnx_to_rknn.py

7. Деплой на устройство
   scp *.rknn root@device:/opt/traffic_ai/models/
```

## Рекомендуемые размеры датасетов

| Модель          | Мин. изображений | Рекомендуется |
|-----------------|------------------|---------------|
| vehicle YOLOv8n | 500 (finetune)   | 2 000         |
| plate YOLOv8n   | 1 000            | 5 000         |
| LPRNet кирилл.  | NOMEROFF-NET ~50k | —             |
| seatbelt MBv2   | 1 000 / класс    | 3 000 / класс |
| phone YOLOv8n   | 300 (finetune)   | 1 000         |
