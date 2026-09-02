#!/usr/bin/env python3
"""
Дообучение LPRNet на кириллические номера РФ/BY/KZ.

Датасет: NOMEROFF-NET (https://github.com/ria-com/nomeroff-net)
  - Содержит размеченные номера RU, BY, KZ, UA с кириллицей
  - Скачать: python -m nomeroff_net.tools.download_dataset

Архитектура LPRNet:
  - Backbone: SqueezeNet-style (малый вес, быстро)
  - Вход: 94×24 grayscale
  - Выход: CTC sequence (макс. 8 символов)
  - Алфавит RU: А-Я без Ё, 0-9, регионные коды → 36 символов + blank

Usage:
    python training/lpr/train_lprnet.py \
        --dataset training/datasets/lprnet/ \
        --epochs 100 \
        --pretrained runs/lprnet/pretrained.pth
"""

import argparse
import os
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

# Кириллический алфавит для номеров РФ
RU_ALPHABET = [
    '-',                                        # CTC blank
    'А', 'В', 'Е', 'К', 'М', 'Н', 'О', 'Р',  # допустимые буквы
    'С', 'Т', 'У', 'Х',
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    # Регионные коды (цифры уже включены выше)
]
CHARS = RU_ALPHABET
NUM_CHARS = len(CHARS)
CHAR2IDX = {c: i for i, c in enumerate(CHARS)}
IMG_W, IMG_H = 94, 24


class PlateDataset(Dataset):
    """
    Ожидаемая структура:
        datasets/lprnet/
        ├── train/
        │   ├── А123БВ77.jpg
        │   └── ...
        └── val/
            └── ...
    Имя файла (без расширения) = номер на пластине.
    """
    def __init__(self, root: str, split: str = "train"):
        import torchvision.transforms as T
        self.paths = sorted(Path(root, split).glob("*.jpg"))
        self.transform = T.Compose([
            T.Grayscale(),
            T.Resize((IMG_H, IMG_W)),
            T.ToTensor(),
            T.Normalize([0.5], [0.5]),
        ])

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        from PIL import Image
        path = self.paths[idx]
        label_str = path.stem.upper()
        image = self.transform(Image.open(path).convert("RGB"))
        label = torch.tensor(
            [CHAR2IDX.get(c, 0) for c in label_str], dtype=torch.long
        )
        return image, label, len(label)


def collate_fn(batch):
    images, labels, lengths = zip(*batch)
    images = torch.stack(images)
    labels_cat = torch.cat(labels)
    lengths = torch.tensor(lengths, dtype=torch.long)
    return images, labels_cat, lengths


class LPRNet(nn.Module):
    def __init__(self, num_chars: int):
        super().__init__()
        self.backbone = nn.Sequential(
            nn.Conv2d(1, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.MaxPool2d(2, 2),                               # 47×12
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
            nn.MaxPool2d((2, 1)),                             # 47×6
            nn.Conv2d(128, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(),
            nn.Conv2d(256, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(),
            nn.MaxPool2d((2, 1)),                             # 47×3
            nn.Conv2d(256, 512, 3, padding=(0, 1)), nn.BatchNorm2d(512), nn.ReLU(),
        )
        self.classifier = nn.Linear(512, num_chars)

    def forward(self, x):
        # x: [B, 1, H, W]
        feat = self.backbone(x)               # [B, 512, 1, W']
        feat = feat.squeeze(2)                # [B, 512, W']
        feat = feat.permute(2, 0, 1)         # [W', B, 512]  — time-first for CTC
        return self.classifier(feat)          # [W', B, num_chars]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset",    default="training/datasets/lprnet/")
    p.add_argument("--epochs",     type=int, default=100)
    p.add_argument("--batch",      type=int, default=64)
    p.add_argument("--lr",         type=float, default=1e-3)
    p.add_argument("--device",     default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--pretrained", default=None, help="Загрузить веса для дообучения")
    p.add_argument("--out",        default="runs/lprnet/best.pth")
    return p.parse_args()


def train(args):
    device = torch.device(args.device)

    train_ds = PlateDataset(args.dataset, "train")
    val_ds   = PlateDataset(args.dataset, "val")
    train_dl = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                          collate_fn=collate_fn, num_workers=4)
    val_dl   = DataLoader(val_ds, batch_size=args.batch,
                          collate_fn=collate_fn, num_workers=2)

    model = LPRNet(NUM_CHARS).to(device)
    if args.pretrained:
        model.load_state_dict(torch.load(args.pretrained, map_location=device))
        print(f"Loaded pretrained: {args.pretrained}")

    ctc_loss = nn.CTCLoss(blank=0, zero_infinity=True)
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs)

    best_acc = 0.0
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, args.epochs + 1):
        # Train
        model.train()
        total_loss = 0.0
        for images, labels, lengths in train_dl:
            images = images.to(device)
            labels = labels.to(device)
            logits = model(images)                          # [T, B, C]
            log_probs = logits.log_softmax(2)
            input_lengths = torch.full(
                (images.size(0),), logits.size(0), dtype=torch.long
            )
            loss = ctc_loss(log_probs, labels, input_lengths, lengths)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            total_loss += loss.item()
        scheduler.step()

        # Validate (sequence accuracy)
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for images, labels, lengths in val_dl:
                images = images.to(device)
                logits = model(images).argmax(2)            # [T, B]
                preds = logits.permute(1, 0)               # [B, T]
                offset = 0
                for i, length in enumerate(lengths.tolist()):
                    gt = labels[offset:offset + length].tolist()
                    pred_seq = []
                    prev = -1
                    for c in preds[i].tolist():
                        if c != 0 and c != prev:
                            pred_seq.append(c)
                        prev = c
                    correct += int(pred_seq == gt)
                    total  += 1
                    offset += length

        acc = correct / max(total, 1)
        print(f"Epoch {epoch:3d}/{args.epochs}  loss={total_loss/len(train_dl):.4f}"
              f"  val_acc={acc:.3f}")

        if acc > best_acc:
            best_acc = acc
            torch.save(model.state_dict(), args.out)
            print(f"  → saved best ({acc:.3f})")

    print(f"\nBest val accuracy: {best_acc:.3f}")
    print(f"Weights: {args.out}")
    print("Next: export to ONNX:")
    print(f"  python -c \"import torch; m=LPRNet({NUM_CHARS}); "
          f"m.load_state_dict(torch.load('{args.out}')); "
          f"torch.onnx.export(m, torch.zeros(1,1,{IMG_H},{IMG_W}), 'lprnet.onnx')\"")


def main():
    train(parse_args())


if __name__ == "__main__":
    main()
