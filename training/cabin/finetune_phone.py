#!/usr/bin/env python3
"""
Дообучение YOLOv8n для детекции телефона в кабине автомобиля.

Базовые веса: yolov8n.pt (COCO pretrained, класс 67 = cell phone).
Дообучение добавляет примеры из кабины (сложный фон, частичная окклюзия,
разные ракурсы, ночные снимки).

Структура датасета:
    datasets/phone/
    ├── images/
    │   ├── train/   *.jpg  (кроп зоны рук водителя)
    │   └── val/     *.jpg
    ├── labels/
    │   ├── train/   *.txt  (YOLO: 0 cx cy w h)
    │   └── val/     *.txt
    └── data.yaml

Usage:
    python training/cabin/finetune_phone.py \
        --data training/datasets/phone/data.yaml \
        --epochs 40 \
        --batch 16
"""

import argparse
from pathlib import Path


DATA_YAML_TEMPLATE = """
path: {abs_path}
train: images/train
val:   images/val

nc: 1
names: ['phone']
"""


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data",    default="training/datasets/phone/data.yaml")
    p.add_argument("--epochs",  type=int, default=40)
    p.add_argument("--imgsz",   type=int, default=640)
    p.add_argument("--batch",   type=int, default=16)
    p.add_argument("--device",  default="0")
    p.add_argument("--weights", default="yolov8n.pt")
    p.add_argument("--project", default="runs/phone")
    p.add_argument("--name",    default="finetune")
    p.add_argument("--init-yaml", action="store_true")
    return p.parse_args()


def init_yaml(data_path: str):
    path = Path(data_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        DATA_YAML_TEMPLATE.format(abs_path=path.parent.resolve()).strip()
    )
    print(f"Created: {path}")


def train(args):
    from ultralytics import YOLO

    model = YOLO(args.weights)
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        # Акцент на мелкие объекты в нижней части кадра
        lr0=0.0005,
        lrf=0.01,
        warmup_epochs=3,
        hsv_v=0.4,          # яркость: ночные снимки
        mosaic=0.5,
        scale=0.3,
        translate=0.1,
        fliplr=0.3,
        flipud=0.0,
    )
    best = Path(results.save_dir) / "weights" / "best.pt"
    print(f"\nBest weights: {best}")
    print(f"Export: yolo export model={best} format=onnx imgsz={args.imgsz}")


def main():
    args = parse_args()
    if args.init_yaml:
        init_yaml(args.data)
    else:
        train(args)


if __name__ == "__main__":
    main()
