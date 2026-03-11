# Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#
# Copyright (c) 2026 Chengdu Changshu Robot Co., Ltd.
# https://www.openarmx.com
#
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike
# 4.0 International License (CC BY-NC-SA 4.0).
#
# To view a copy of this license, visit:
# http://creativecommons.org/licenses/by-nc-sa/4.0/
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

"""独立的 OpenCV 相机枚举与实时查看工具。

- 自动探测可用相机（默认尝试 0..N）。
- 每路相机开一个窗口，叠加 index/path 与 FPS。
- 任意窗口按 `q` 退出。
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenArmX OpenCV camera viewer")
    parser.add_argument(
        "--cams",
        nargs="+",
        help="自定义相机源（如 0 1 /dev/video4 或 video.mp4）；不写则自动探测 0..max-index",
    )
    parser.add_argument("--max-index", type=int, default=5, help="自动探测最大索引（包含）")
    parser.add_argument("--width", type=int, help="强制输出宽度")
    parser.add_argument("--height", type=int, help="强制输出高度")
    parser.add_argument("--fps", type=int, help="强制 FPS")
    parser.add_argument("--rotation", type=int, default=0, choices=[0, 90, 180, 270], help="旋转角度")
    return parser.parse_args()


def detect_cameras(max_index: int) -> list[int]:
    """简单探测 0..max_index，能读到一帧即认为可用。"""
    found: list[int] = []
    for i in range(max_index + 1):
        cap = cv2.VideoCapture(i)
        ok, frame = cap.read()
        if ok and frame is not None:
            found.append(i)
        cap.release()
    return found


def open_capture(index_or_path: Any, width: int | None, height: int | None, fps: int | None) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index_or_path)
    if fps:
        cap.set(cv2.CAP_PROP_FPS, fps)
    if width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap


def rotate_image(frame, degrees: int):
    if degrees == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def main() -> None:
    args = parse_args()

    if args.cams:
        camera_sources: list[Any] = [str(Path(c)) if Path(c).exists() else c for c in args.cams]
    else:
        detected = detect_cameras(args.max_index)
        camera_sources = detected
        if not detected:
            raise SystemExit(f"未探测到可用相机（尝试 0..{args.max_index}）。可用 --cams 手动指定。")

    caps: list[tuple[str, cv2.VideoCapture]] = []
    for idx, src in enumerate(camera_sources):
        cap = open_capture(src, args.width, args.height, args.fps)
        caps.append((f"cam_{idx}", cap))

    last_time = time.time()
    frame_count = 0
    fps = 0.0

    while True:
        for name, cap in caps:
            ok, frame = cap.read()
            if not ok or frame is None:
                frame = np.full((240, 320, 3), 32, dtype=np.uint8)
                cv2.putText(
                    frame,
                    f"{name}: {camera_sources[int(name.split('_')[-1])]} not available",
                    (8, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    frame,
                    "检查连接或用 --cams 覆盖。",
                    (8, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1,
                    cv2.LINE_AA,
                )
            else:
                frame = rotate_image(frame, args.rotation)
                text = f"{name}: {camera_sources[int(name.split('_')[-1])]}"
                cv2.putText(frame, text, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)
                cv2.putText(frame, f"{fps:.1f} FPS", (8, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)
            try:
                cv2.imshow(name, frame)
            except cv2.error as e:
                raise SystemExit(
                    "OpenCV GUI 不可用，需安装带 HighGUI 的版本（例如 `pip install --upgrade opencv-python`）。"
                ) from e

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        frame_count += 1
        now = time.time()
        if now - last_time >= 1.0:
            fps = frame_count / (now - last_time)
            frame_count = 0
            last_time = now

    for _, cap in caps:
        cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
