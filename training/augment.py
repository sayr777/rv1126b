#!/usr/bin/env python3
"""
Аугментация датасета для дообучения моделей детекции и классификации.

Usage:
    python training/augment.py \
        --src  training/datasets/raw/front/ \
        --dst  training/datasets/augmented/front/ \
        --mode detection \
        --factor 5

Режимы:
  detection    — сохраняет YOLO-лейблы (.txt) вместе с изображениями
  classification — только изображения (для MobileNetV2)
"""

import argparse
import os
import random
from pathlib import Path

import cv2
import albumentations as A


DETECTION_PIPELINE = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.RandomBrightnessContrast(brightness_limit=0.3, contrast_limit=0.3, p=0.7),
    A.HueSaturationValue(hue_shift_limit=10, sat_shift_limit=30, val_shift_limit=20, p=0.5),
    A.GaussNoise(var_limit=(10, 50), p=0.4),
    A.MotionBlur(blur_limit=5, p=0.3),
    A.RandomRain(p=0.15),
    A.RandomFog(p=0.10),
    A.RandomShadow(p=0.20),
    A.Rotate(limit=5, p=0.3),
], bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"]))

CLASSIFICATION_PIPELINE = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.RandomBrightnessContrast(brightness_limit=0.35, contrast_limit=0.35, p=0.8),
    A.HueSaturationValue(p=0.5),
    A.GaussNoise(var_limit=(5, 40), p=0.4),
    A.MotionBlur(blur_limit=5, p=0.3),
    A.RandomShadow(p=0.3),
    A.CoarseDropout(max_holes=4, max_height=32, max_width=32, p=0.3),
])


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--src",    required=True)
    p.add_argument("--dst",    required=True)
    p.add_argument("--mode",   choices=["detection", "classification"], default="detection")
    p.add_argument("--factor", type=int, default=5,
                   help="Количество аугментированных копий на каждый оригинал")
    p.add_argument("--seed",   type=int, default=42)
    return p.parse_args()


def load_yolo_labels(label_path: str):
    boxes, classes = [], []
    if not os.path.exists(label_path):
        return boxes, classes
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 5:
                cls = int(parts[0])
                coords = list(map(float, parts[1:]))
                classes.append(cls)
                boxes.append(coords)
    return boxes, classes


def save_yolo_labels(label_path: str, boxes, classes):
    with open(label_path, "w") as f:
        for cls, box in zip(classes, boxes):
            f.write(f"{cls} {' '.join(f'{v:.6f}' for v in box)}\n")


def augment_detection(src: Path, dst: Path, factor: int):
    dst.mkdir(parents=True, exist_ok=True)
    images = list(src.glob("*.jpg")) + list(src.glob("*.png"))
    print(f"Detection augmentation: {len(images)} source images × {factor} → {dst}")

    for img_path in images:
        label_path = img_path.with_suffix(".txt")
        image = cv2.imread(str(img_path))
        boxes, classes = load_yolo_labels(str(label_path))

        # Save original
        cv2.imwrite(str(dst / img_path.name), image)
        if boxes:
            save_yolo_labels(str(dst / label_path.name), boxes, classes)

        for i in range(factor):
            transformed = DETECTION_PIPELINE(
                image=image,
                bboxes=boxes,
                class_labels=classes,
            )
            stem = f"{img_path.stem}_aug{i:03d}"
            out_img = dst / f"{stem}.jpg"
            cv2.imwrite(str(out_img), transformed["image"],
                        [cv2.IMWRITE_JPEG_QUALITY, 92])
            if transformed["bboxes"]:
                save_yolo_labels(
                    str(dst / f"{stem}.txt"),
                    transformed["bboxes"],
                    transformed["class_labels"],
                )

    print(f"Done. {len(images) * (factor + 1)} images in {dst}")


def augment_classification(src: Path, dst: Path, factor: int):
    for cls_dir in src.iterdir():
        if not cls_dir.is_dir():
            continue
        out_cls = dst / cls_dir.name
        out_cls.mkdir(parents=True, exist_ok=True)
        images = list(cls_dir.glob("*.jpg")) + list(cls_dir.glob("*.png"))
        print(f"  [{cls_dir.name}] {len(images)} images × {factor}")
        for img_path in images:
            image = cv2.imread(str(img_path))
            cv2.imwrite(str(out_cls / img_path.name), image)
            for i in range(factor):
                transformed = CLASSIFICATION_PIPELINE(image=image)["image"]
                out = out_cls / f"{img_path.stem}_aug{i:03d}.jpg"
                cv2.imwrite(str(out), transformed, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"Done. Augmented dataset in {dst}")


def main():
    args = parse_args()
    random.seed(args.seed)
    src, dst = Path(args.src), Path(args.dst)
    if args.mode == "detection":
        augment_detection(src, dst, args.factor)
    else:
        augment_classification(src, dst, args.factor)


if __name__ == "__main__":
    main()
