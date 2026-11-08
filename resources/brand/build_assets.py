#!/usr/bin/env python3
"""Dựng PNG/favicon/OG từ SVG logo. Chạy trên macOS (qlmanage) + Pillow.

    .venv/bin/python resources/brand/build_assets.py

Nguồn duy nhất: vifasttts-icon.svg và vifasttts-lockup.svg.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import label

ROOT = Path(__file__).resolve().parent
FONTS = Path("/System/Library/Fonts/Supplemental")
CREAM = "#FFF8EC"
RED = "#C6281E"
GOLD = "#C98A00"
INK = "#1F2430"
MUTED = "#6B7280"


def ql_render(svg: Path, size: int) -> Path:
    subprocess.run(
        ["qlmanage", "-t", "-s", str(size), "-o", str(svg.parent), str(svg)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return svg.with_suffix(svg.suffix + ".png")


def rounded_icon(size: int) -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "icon.svg"
        src.write_text((ROOT / "vifasttts-icon.svg").read_text(encoding="utf-8"), encoding="utf-8")
        png = ql_render(src, size)
        im = Image.open(png).convert("RGBA")
    mask = Image.new("L", (size * 4, size * 4), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size * 4 - 1, size * 4 - 1], radius=112 / 512 * size * 4, fill=255)
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)
    im.putalpha(mask)
    return im


def transparent_lockup() -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp:
        inner = re.sub(r"^<svg[^>]*>", "", (ROOT / "vifasttts-lockup.svg").read_text(encoding="utf-8"))
        inner = inner.replace("</svg>", "")
        wrapper = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1400" '
            'viewBox="0 0 1400 1400">\n'
            f'<g transform="translate(0,500)">{inner}</g>\n</svg>'
        )
        src = Path(tmp) / "lockup.svg"
        src.write_text(wrapper, encoding="utf-8")
        png = ql_render(src, 1400)
        im = Image.open(png).convert("RGBA").crop((0, 500, 1400, 900))
    # Nền trắng do qlmanage sinh ra: chỉ xoá vùng trắng nối với biên.
    import numpy as np
    arr = np.array(im)
    rgb = arr[:, :, :3].astype(np.int16)
    near_white = (rgb[:, :, 0] > 244) & (rgb[:, :, 1] > 244) & (rgb[:, :, 2] > 244)
    labels, _ = label(near_white, structure=np.ones((3, 3), dtype=int))
    border = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    background = np.isin(labels, list(border))
    arr[:, :, 3] = np.where(background, 0, 255)
    return Image.fromarray(arr, "RGBA")


def og_image(lockup: Image.Image) -> Image.Image:
    im = Image.new("RGB", (1200, 630), CREAM)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1200, 12], fill="#D42A20")
    d.rectangle([0, 12, 1200, 18], fill="#FFB800")
    logo = lockup.copy()
    logo.thumbnail((1080, 330), Image.Resampling.LANCZOS)
    im.paste(logo, ((1200 - logo.width) // 2, 130), logo)
    f_big = ImageFont.truetype(str(FONTS / "Arial Bold.ttf"), 30)
    f_small = ImageFont.truetype(str(FONTS / "Arial.ttf"), 24)
    d.text((600, 500), "TTS tiếng Việt · nhỏ · nhanh · chạy CPU", font=f_big, fill=INK, anchor="mm")
    d.text((600, 548), "tts.vifast.org", font=f_small, fill=RED, anchor="mm")
    d.text((600, 590), "ONNX CPU · 24 kHz · small 6,1M", font=f_small, fill=MUTED, anchor="mm")
    return im


def main() -> None:
    icon = rounded_icon(1024)
    icon.resize((512, 512), Image.Resampling.LANCZOS).save(ROOT / "vifasttts-icon-512.png")
    icon.resize((192, 192), Image.Resampling.LANCZOS).save(ROOT / "vifasttts-icon-192.png")
    icon.resize((32, 32), Image.Resampling.LANCZOS).save(ROOT / "favicon-32.png")
    icon.resize((16, 16), Image.Resampling.LANCZOS).save(ROOT / "favicon-16.png")
    icon.resize((256, 256), Image.Resampling.LANCZOS).save(
        ROOT / "favicon.ico", format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    # Apple touch icon: nền đỏ full-bleed, Apple tự bo góc.
    apple = Image.new("RGB", (180, 180), "#D42A20")
    apple.paste(icon.resize((180, 180), Image.Resampling.LANCZOS), (0, 0), icon.resize((180, 180), Image.Resampling.LANCZOS))
    apple.save(ROOT / "apple-touch-icon.png")

    lockup = transparent_lockup()
    lockup.save(ROOT / "vifasttts-lockup.png")
    cream = Image.new("RGBA", lockup.size, (255, 248, 236, 255))
    cream.alpha_composite(lockup)
    cream.convert("RGB").save(ROOT / "vifasttts-lockup-cream.png")
    og_image(lockup).save(ROOT / "og-image.png", optimize=True)

    print("wrote", ROOT)


if __name__ == "__main__":
    main()
