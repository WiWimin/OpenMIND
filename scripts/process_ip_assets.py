# -*- coding: utf-8 -*-
"""生成前端 IP 吉祥物透明 PNG。

处理 resources/ 下的白底 JPEG（豆包生成，含水印）：
1. 定位"台沿"线（鹦鹉趴伏的水平线），裁掉台沿以下与右下角水印；
2. 从图像边缘种子点泛洪填充去白底（只移除与边界连通的白色，
   鹦鹉白脸/白肚被蓝色轮廓包裹不受影响）；
3. 按非透明 bbox 裁紧、等比缩放到目标高度，输出 PNG。

用法（开发机一次性执行）：
    pip install pillow
    python scripts/process_ip_assets.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
RESOURCES = ROOT / "resources"
OUT_DIR = ROOT / "frontend" / "src" / "assets" / "ip"

# 泛洪判定：与种子色差异小于该值视为同一区域（覆盖 JPEG 白噪与浅灰阴影）
FLOOD_THRESHOLD = 42
SENTINEL = (255, 0, 255)

# 输出目标高度（2x 清晰度）
TARGET_HEIGHT = {"assistant-parrot": 220, "memory-parrot": 240}


def is_near_white(px: tuple[int, int, int]) -> bool:
    return px[0] > 235 and px[1] > 235 and px[2] > 235


def find_ledge_y(image: Image.Image) -> int:
    """从底部向上找第一条横贯全宽的"台沿"线（大量非白像素的行）。"""
    gray = image.convert("L")
    width, height = gray.size
    pixels = gray.load()
    for y in range(height - 1, height // 2, -1):
        count = sum(1 for x in range(width) if pixels[x, y] < 235)
        if count > width * 0.5:
            return y
    return height


def remove_background(image: Image.Image) -> Image.Image:
    """边缘种子泛洪：与边界连通的近白区域全部置为透明。"""
    rgb = image.convert("RGB")
    width, height = rgb.size
    seeds = [
        (0, 0),
        (width - 1, 0),
        (0, height - 1),
        (width - 1, height - 1),
        (width // 2, 0),
        (width // 2, height - 1),
        (0, height // 2),
        (width - 1, height // 2),
    ]
    # 四角与四边中点中，实际是白色的才作为种子
    seeds = [p for p in seeds if is_near_white(rgb.getpixel(p))]
    for seed in seeds:
        ImageDraw.floodfill(rgb, seed, SENTINEL, thresh=FLOOD_THRESHOLD)

    rgba = rgb.convert("RGBA")
    data = rgba.load()
    for y in range(height):
        for x in range(width):
            if data[x, y][:3] == SENTINEL:
                data[x, y] = (0, 0, 0, 0)
    return rgba


def process(source: Path, name: str) -> Path:
    image = Image.open(source).convert("RGB")

    # 1. 裁掉台沿以下（含水印）：定位台沿线，保留指尖搭沿的 2px 余量
    ledge_y = find_ledge_y(image)
    image = image.crop((0, 0, image.width, min(ledge_y + 2, image.height)))

    # 2. 去白底 + 裁紧边界
    transparent = remove_background(image)
    bbox = transparent.getbbox()
    transparent = transparent.crop(bbox)

    # 3. 等比缩放到目标高度
    target_height = TARGET_HEIGHT[name]
    ratio = target_height / transparent.height
    target_size = (max(1, round(transparent.width * ratio)), target_height)
    transparent = transparent.resize(target_size, Image.LANCZOS)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{name}.png"
    transparent.save(out_path, optimize=True)
    print(f"{source.name} -> {out_path.relative_to(ROOT)} size={transparent.size}")
    return out_path


if __name__ == "__main__":
    process(RESOURCES / "input-ip.jpeg", "assistant-parrot")
    process(RESOURCES / "memory-ip.jpeg", "memory-parrot")
