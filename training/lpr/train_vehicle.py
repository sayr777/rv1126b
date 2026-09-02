#!/usr/bin/env python3
"""
Дообучение YOLOv8n на детекцию автомобилей в условиях РФ.

Базовые веса: yolov8n.pt (COCO pretrained).
Классы: car, bus, truck (переиндексированы в 0, 1, 2).

Структура датасета (YOLO формат):
    datasets/vehicle/
    ├── images/
    │   ├── train/   *.jpg
    │   └── val/     *.jpg
    ├── labels/
    │   ├── train/   *.txt   (YOLO: cls cx cy w h)
    │   └── val/     *.txt
    └── data.yaml

Usage:
    python training/lpr/train_vehicle.py \
        --data training/datasets/vehicle/data.yaml \
        --epochs 50 \
        --imgsz 640 \
        --batch 16 \
        --device 0
"""

import argparse
from pathlib import Path


DATA_YAML_TEMPLATE = """
path: {abs_path}
train: images/train
val:   images/val

nc: 3
names: ['car', 'bus', 'truck']
"""


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data",    default="training/datasets/vehicle/data.yaml")
    p.add_argument("--epochs",  type=int, default=50)
    p.add_argument("--imgsz",   type=int, default=640)
    p.add_argument("--batch",   type=int, default=16)
    p.add_argument("--device",  default="0", help="GPU id or 'cpu'")
    p.add_argument("--weights", default="yolov8n.pt",
                   help="Starting weights (COCO pretrained)")
    p.add_argument("--project", default="runs/vehicle")
    p.add_argument("--name",    default="finetune")
    p.add_argument("--init-yaml", action="store_true",
                   help="Create data.yaml template and exit")
    return p.parse_args()


def init_yaml(data_path: str):
    path = Path(data_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    abs_path = path.parent.resolve()
    path.write_text(DATA_YAML_TEMPLATE.format(abs_path=abs_path).strip())
    print(f"Created: {path}")
    print("Fill in images/ and labels/ directories, then run without --init-yaml")


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
        # Оптимизированные гиперпараметры для дообучения
        lr0=0.001,
        lrf=0.01,
        warmup_epochs=3,
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.3,
        flipud=0.0,
        fliplr=0.5,
        mosaic=0.8,
        mixup=0.1,
        copy_paste=0.0,
    )
    best = Path(results.save_dir) / "weights" / "best.pt"
    print(f"\nBest weights: {best}")
    print("Next step: export to ONNX then RKNN:")
    print(f"  yolo export model={best} format=onnx imgsz={args.imgsz}")
    print(f"  python models/convert/convert_onnx_to_rknn.py \\")
    print(f"    --model {best.with_suffix('.onnx')} \\")
    print(f"    --output models/vehicle_yolov8n.rknn \\")
    print(f"    --calib training/datasets/calibration/")


def main():
    args = parse_args()
    if args.init_yaml:
        init_yaml(args.data)
    else:
        train(args)


if __name__ == "__main__":
    main()
