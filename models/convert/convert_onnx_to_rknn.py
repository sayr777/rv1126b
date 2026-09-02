#!/usr/bin/env python3
"""
Convert ONNX model to RKNN INT8 for Rockchip RV1126B NPU.

Usage:
    python models/convert/convert_onnx_to_rknn.py \
        --model  yolov8n.onnx \
        --output models/vehicle_yolov8n.rknn \
        --calib  training/datasets/calibration/ \
        --target rk1126b

Requirements (host PC only, NOT on the device):
    pip install rknn-toolkit2 onnx
"""

import argparse
import os
from pathlib import Path


SUPPORTED_TARGETS = ["rk1126b", "rk3588", "rk3568", "rk3566", "rk1808"]

# Preprocessing defaults for YOLO (ImageNet-normalized)
YOLO_MEAN = [[0.0, 0.0, 0.0]]
YOLO_STD  = [[255.0, 255.0, 255.0]]

# Preprocessing defaults for MobileNetV2 / classifiers
MBV2_MEAN = [[123.675, 116.28, 103.53]]
MBV2_STD  = [[58.395, 57.12, 57.375]]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--model",  required=True, help="Input .onnx model")
    p.add_argument("--output", required=True, help="Output .rknn path")
    p.add_argument("--calib",  required=True, help="Dir with calibration images (JPG/PNG)")
    p.add_argument("--target", default="rk1126b", choices=SUPPORTED_TARGETS)
    p.add_argument("--preset", default="yolo",
                   choices=["yolo", "mbv2", "lprnet", "custom"],
                   help="Preprocessing preset")
    p.add_argument("--mean", nargs=3, type=float, default=None,
                   help="Override mean (r g b)")
    p.add_argument("--std",  nargs=3, type=float, default=None,
                   help="Override std (r g b)")
    p.add_argument("--calib-n", type=int, default=200,
                   help="Max calibration images to use")
    return p.parse_args()


def get_preprocessing(args):
    if args.mean and args.std:
        return [args.mean], [args.std]
    if args.preset == "mbv2":
        return MBV2_MEAN, MBV2_STD
    if args.preset in ("yolo", "lprnet"):
        return YOLO_MEAN, YOLO_STD
    return YOLO_MEAN, YOLO_STD


def collect_calib_images(calib_dir: str, n: int):
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    imgs = sorted(
        str(p) for p in Path(calib_dir).rglob("*") if p.suffix.lower() in exts
    )
    if len(imgs) < 20:
        raise RuntimeError(f"Too few calibration images in {calib_dir}: {len(imgs)}")
    return imgs[:n]


def main():
    args = parse_args()
    from rknn.api import RKNN

    mean, std = get_preprocessing(args)
    rknn = RKNN(verbose=False)

    rknn.config(
        mean_values=mean,
        std_values=std,
        target_platform=args.target,
        quantized_dtype="asymmetric_quantized_u8",
        optimization_level=3,
    )

    print(f"[1/4] Loading {args.model}")
    ret = rknn.load_onnx(model=args.model)
    assert ret == 0, f"load_onnx failed: {ret}"

    calib_imgs = collect_calib_images(args.calib, args.calib_n)
    print(f"[2/4] Building INT8 with {len(calib_imgs)} calibration images ...")
    ret = rknn.build(do_quantization=True, dataset=calib_imgs)
    assert ret == 0, f"build failed: {ret}"

    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    print(f"[3/4] Exporting → {args.output}")
    ret = rknn.export_rknn(args.output)
    assert ret == 0, f"export_rknn failed: {ret}"

    print(f"[4/4] Done. Model saved: {args.output}")
    rknn.release()


if __name__ == "__main__":
    main()
