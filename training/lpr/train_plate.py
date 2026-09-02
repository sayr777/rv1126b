#!/usr/bin/env python3
"""
Обучение YOLOv8n на детекцию номерных знаков РФ.

Датасеты:
  - CCPD2020  (Chinese plates, структура рамки аналогична)
  - Собственный сбор через training/collect_frames.py

Один класс: plate (0).
Вход модели: 320×192 (соотношение 5:3 под горизонтальный номер).

Структура датасета:
    datasets/plate/
    ├── images/train/   *.jpg  (кропы авто, 320×192)
    ├── images/val/     *.jpg
    ├── labels/train/   *.txt  (YOLO: 0 cx cy w h)
    ├── labels/val/     *.txt
    └── data.yaml

Usage:
    python training/lpr/train_plate.py \
        --data training/datasets/plate/data.yaml \
        --epochs 80 \
        --imgsz 320
"""

import argparse
from pathlib import Path


DATA_YAML_TEMPLATE = """
path: {abs_path}
train: images/train
val:   images/val

nc: 1
names: ['plate']
"""


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data",    default="training/datasets/plate/data.yaml")
    p.add_argument("--epochs",  type=int, default=80)
    p.add_argument("--imgsz",   type=int, default=320)
    p.add_argument("--batch",   type=int, default=32)
    p.add_argument("--device",  default="0")
    p.add_argument("--weights", default="yolov8n.pt")
    p.add_argument("--project", default="runs/plate")
    p.add_argument("--name",    default="train")
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
        rect=True,          # прямоугольный батч (320×192, не квадрат)
        lr0=0.002,
        lrf=0.01,
        warmup_epochs=5,
        degrees=3.0,        # небольшой поворот (наклон камеры)
        perspective=0.0003,
        mosaic=1.0,
        scale=0.5,
    )
    best = Path(results.save_dir) / "weights" / "best.pt"
    print(f"\nBest weights: {best}")
    print(f"Export: yolo export model={best} format=onnx imgsz=[192,320]")


def main():
    args = parse_args()
    if args.init_yaml:
        init_yaml(args.data)
    else:
        train(args)


if __name__ == "__main__":
    main()
