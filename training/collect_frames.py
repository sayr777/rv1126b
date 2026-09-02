#!/usr/bin/env python3
"""
Сбор кадров с устройства для формирования датасета.

Режимы:
  rtsp   — захват кадров из RTSP-потока камеры
  ssh    — копирование уже накопленных снимков с устройства по SSH

Usage:
    python training/collect_frames.py rtsp \
        --url rtsp://10.0.0.5:8554/front \
        --out training/datasets/raw/front/ \
        --interval 2.0 \
        --limit 500

    python training/collect_frames.py ssh \
        --host 10.0.0.5 --user root \
        --remote /opt/traffic_ai/snapshots/ \
        --out training/datasets/raw/snapshots/
"""

import argparse
import os
import time
from pathlib import Path
from datetime import datetime


def parse_args():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)

    rtsp = sub.add_parser("rtsp", help="Захват из RTSP-потока")
    rtsp.add_argument("--url",      required=True)
    rtsp.add_argument("--out",      required=True)
    rtsp.add_argument("--interval", type=float, default=1.0,
                      help="Секунд между кадрами")
    rtsp.add_argument("--limit",    type=int, default=1000)

    ssh = sub.add_parser("ssh", help="Копирование снимков по SSH")
    ssh.add_argument("--host",   required=True)
    ssh.add_argument("--user",   default="root")
    ssh.add_argument("--remote", required=True,
                     help="Удалённый путь к папке со снимками")
    ssh.add_argument("--out",    required=True)

    return p.parse_args()


def collect_rtsp(url: str, out_dir: str, interval: float, limit: int):
    import cv2
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open RTSP stream: {url}")

    count = 0
    print(f"Capturing from {url} → {out_dir}  (interval={interval}s, limit={limit})")
    try:
        while count < limit:
            ret, frame = cap.read()
            if not ret:
                print("Stream ended or error — retrying in 2s")
                time.sleep(2)
                cap = cv2.VideoCapture(url)
                continue

            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = os.path.join(out_dir, f"{ts}.jpg")
            cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            count += 1
            print(f"  [{count}/{limit}] saved {path}")
            time.sleep(interval)
    finally:
        cap.release()

    print(f"Done. {count} frames saved to {out_dir}")


def collect_ssh(host: str, user: str, remote: str, out_dir: str):
    import subprocess
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    src = f"{user}@{host}:{remote.rstrip('/')}/"
    cmd = ["rsync", "-avz", "--include=*.jpg", "--include=*.png",
           "--exclude=*", src, out_dir]
    print(f"rsync {src} → {out_dir}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError("rsync failed")
    print("Done.")


def main():
    args = parse_args()
    if args.mode == "rtsp":
        collect_rtsp(args.url, args.out, args.interval, args.limit)
    else:
        collect_ssh(args.host, args.user, args.remote, args.out)


if __name__ == "__main__":
    main()
