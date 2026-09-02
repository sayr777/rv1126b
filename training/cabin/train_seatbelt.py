#!/usr/bin/env python3
"""
Обучение бинарного классификатора ремня безопасности.

Архитектура: MobileNetV2 (ImageNet pretrained) → finetune head → 2 класса.

Структура датасета:
    datasets/seatbelt/
    ├── train/
    │   ├── belt_on/    *.jpg   (водитель с ремнём)
    │   └── belt_off/   *.jpg   (водитель без ремня)
    └── val/
        ├── belt_on/
        └── belt_off/

Рекомендуемый размер: ≥ 1 500 изображений на класс.
Кадры должны быть сняты с кабинной камеры в условиях реальной эксплуатации.

Usage:
    python training/cabin/train_seatbelt.py \
        --dataset training/datasets/seatbelt/ \
        --epochs 30 \
        --batch 32 \
        --device 0
"""

import argparse
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as T
import torchvision.datasets as datasets
import torchvision.models as models
from torch.utils.data import DataLoader


IMG_SIZE = 224
CLASSES  = ["belt_off", "belt_on"]   # индекс 0 = нарушение, 1 = норма


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="training/datasets/seatbelt/")
    p.add_argument("--epochs",  type=int, default=30)
    p.add_argument("--batch",   type=int, default=32)
    p.add_argument("--lr",      type=float, default=3e-4)
    p.add_argument("--device",  default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--out",     default="runs/seatbelt/best.pt")
    p.add_argument("--freeze-backbone", action="store_true",
                   help="Заморозить backbone, обучать только голову (быстрее)")
    return p.parse_args()


def build_transforms(train: bool):
    if train:
        return T.Compose([
            T.RandomResizedCrop(IMG_SIZE, scale=(0.7, 1.0)),
            T.RandomHorizontalFlip(),
            T.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.2),
            T.RandomGrayscale(p=0.1),
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
    return T.Compose([
        T.Resize(256),
        T.CenterCrop(IMG_SIZE),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])


def build_model(freeze_backbone: bool) -> nn.Module:
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    if freeze_backbone:
        for p in model.features.parameters():
            p.requires_grad = False
    # Заменяем голову на бинарный классификатор
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(in_features, 2),
    )
    return model


def train(args):
    device = torch.device(args.device)

    train_ds = datasets.ImageFolder(Path(args.dataset) / "train",
                                    transform=build_transforms(True))
    val_ds   = datasets.ImageFolder(Path(args.dataset) / "val",
                                    transform=build_transforms(False))

    print(f"Train: {len(train_ds)} images  Val: {len(val_ds)} images")
    print(f"Classes: {train_ds.classes}")

    train_dl = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                          num_workers=4, pin_memory=True)
    val_dl   = DataLoader(val_ds,   batch_size=args.batch,
                          num_workers=2, pin_memory=True)

    # Веса классов для балансировки несбалансированного датасета
    counts = [0] * 2
    for _, lbl in train_ds:
        counts[lbl] += 1
    class_weights = torch.tensor(
        [len(train_ds) / (2 * c) for c in counts], dtype=torch.float
    ).to(device)

    model     = build_model(args.freeze_backbone).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr, weight_decay=1e-4
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs)

    best_acc = 0.0
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        for images, labels in train_dl:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
        scheduler.step()

        model.eval()
        correct = total = 0
        tp = fp = fn = 0   # для метрики belt_off (нарушение)
        with torch.no_grad():
            for images, labels in val_dl:
                images, labels = images.to(device), labels.to(device)
                preds = model(images).argmax(1)
                correct += (preds == labels).sum().item()
                total   += labels.size(0)
                # Нарушение = класс 0 (belt_off)
                tp += ((preds == 0) & (labels == 0)).sum().item()
                fp += ((preds == 0) & (labels == 1)).sum().item()
                fn += ((preds == 1) & (labels == 0)).sum().item()

        acc = correct / total
        prec = tp / max(tp + fp, 1)
        rec  = tp / max(tp + fn, 1)
        f1   = 2 * prec * rec / max(prec + rec, 1e-6)
        print(f"Epoch {epoch:3d}/{args.epochs}  "
              f"loss={running_loss/len(train_dl):.4f}  "
              f"acc={acc:.3f}  prec={prec:.3f}  rec={rec:.3f}  F1={f1:.3f}")

        if acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), args.out)
            print(f"  → saved best (acc={acc:.3f})")

    print(f"\nBest accuracy: {best_acc:.3f}")
    print(f"Weights: {args.out}")
    print("Export to ONNX:")
    print(f"  python -c \"import torch, torchvision; m=torchvision.models.mobilenet_v2(); "
          f"... torch.onnx.export(m, torch.zeros(1,3,{IMG_SIZE},{IMG_SIZE}), 'seatbelt.onnx')\"")


def main():
    train(parse_args())


if __name__ == "__main__":
    main()
