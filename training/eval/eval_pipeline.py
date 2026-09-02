#!/usr/bin/env python3
"""
End-to-end оценка всего конвейера на тестовом видео или наборе кадров.

Метрики:
  LPR        — точность OCR (% верно считанных номеров)
  Вафельная  — precision / recall нарушений (по GT-аннотациям)
  Ремень     — precision / recall / F1
  Телефон    — precision / recall / F1

GT-аннотации: JSON-файл вида:
  [
    {
      "frame": "20260903_101533.jpg",
      "plate": "А123БВ77",
      "violations": ["NO_SEATBELT"],
      "in_zone": false
    },
    ...
  ]

Usage:
    python training/eval/eval_pipeline.py \
        --frames  training/datasets/eval_frames/ \
        --gt      training/datasets/eval_gt.json \
        --device  10.0.0.5 \
        --report  runs/eval/report.json
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--frames", required=True,
                   help="Папка с тестовыми JPEG-кадрами")
    p.add_argument("--gt",     required=True,
                   help="JSON с GT-аннотациями")
    p.add_argument("--host",   default="10.0.0.5",
                   help="IP устройства (отправка кадров по HTTP для инференса)")
    p.add_argument("--port",   type=int, default=8080)
    p.add_argument("--report", default="runs/eval/report.json")
    return p.parse_args()


def send_frame_get_events(frame_path: str, host: str, port: int) -> List[Dict]:
    """
    Отправляет кадр на устройство через debug HTTP endpoint и получает события.
    Устройство должно быть запущено с флагом --eval-mode.
    """
    import urllib.request
    url = f"http://{host}:{port}/eval/frame"
    with open(frame_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "image/jpeg"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def evaluate(args):
    with open(args.gt) as f:
        gt_list = json.load(f)

    frames_dir = Path(args.frames)
    gt_map = {item["frame"]: item for item in gt_list}

    lpr_correct = lpr_total = 0
    belt_tp = belt_fp = belt_fn = 0
    phone_tp = phone_fp = phone_fn = 0
    zone_tp = zone_fp = zone_fn = 0
    errors = []

    for gt in gt_list:
        frame_path = frames_dir / gt["frame"]
        if not frame_path.exists():
            errors.append(f"Missing frame: {frame_path}")
            continue

        try:
            events = send_frame_get_events(str(frame_path), args.host, args.port)
        except Exception as e:
            errors.append(f"{gt['frame']}: {e}")
            continue

        event_types = {ev["type"] for ev in events}
        plates_read = [ev["plate"] for ev in events if ev.get("plate")]

        # LPR
        if gt.get("plate"):
            lpr_total += 1
            if gt["plate"] in plates_read:
                lpr_correct += 1

        # Ремень
        gt_belt = "NO_SEATBELT" in gt.get("violations", [])
        pred_belt = "NO_SEATBELT" in event_types
        if gt_belt and pred_belt:     belt_tp += 1
        elif pred_belt and not gt_belt: belt_fp += 1
        elif gt_belt and not pred_belt: belt_fn += 1

        # Телефон
        gt_phone = "PHONE_IN_HAND" in gt.get("violations", [])
        pred_phone = "PHONE_IN_HAND" in event_types
        if gt_phone and pred_phone:     phone_tp += 1
        elif pred_phone and not gt_phone: phone_fp += 1
        elif gt_phone and not pred_phone: phone_fn += 1

        # Вафельная зона
        gt_zone = gt.get("in_zone", False)
        pred_zone = "WAFFLE_VIOLATION" in event_types
        if gt_zone and pred_zone:     zone_tp += 1
        elif pred_zone and not gt_zone: zone_fp += 1
        elif gt_zone and not pred_zone: zone_fn += 1

    def prf(tp, fp, fn):
        prec = tp / max(tp + fp, 1)
        rec  = tp / max(tp + fn, 1)
        f1   = 2 * prec * rec / max(prec + rec, 1e-9)
        return round(prec, 3), round(rec, 3), round(f1, 3)

    report = {
        "lpr_accuracy": round(lpr_correct / max(lpr_total, 1), 3),
        "lpr_samples":  lpr_total,
        "seatbelt":  dict(zip(["precision", "recall", "f1"],
                              prf(belt_tp,  belt_fp,  belt_fn))),
        "phone":     dict(zip(["precision", "recall", "f1"],
                              prf(phone_tp, phone_fp, phone_fn))),
        "waffle":    dict(zip(["precision", "recall", "f1"],
                              prf(zone_tp,  zone_fp,  zone_fn))),
        "errors":    errors,
    }

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nReport saved: {args.report}")


def main():
    evaluate(parse_args())


if __name__ == "__main__":
    main()
