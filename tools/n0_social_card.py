"""Tạo ảnh social (Facebook) mô tả luồng N0 — không cần asset ngoài."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 1500
BG = (244, 248, 247)
INK = (24, 33, 43)
MUTED = (99, 112, 131)
TEAL = (15, 118, 110)
TEAL_D = (10, 78, 73)
ORANGE = (194, 101, 8)
PURPLE = (98, 70, 160)
GREEN = (28, 120, 76)
WHITE = (255, 255, 255)
LINE = (219, 229, 232)
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BOLD if bold else FONT, size)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=fnt) <= width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def box(draw, xy, fill, radius=18, outline=None):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=2)


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # faint top band
    d.rectangle((0, 0, W, 12), fill=TEAL)
    x0, bw = 150, 900
    d.text((80, 55), "ViFastTTS  /  N0", font=font(24, True), fill=TEAL)
    d.text((80, 92), "TTS tiếng Việt nhỏ,", font=font(58, True), fill=INK)
    d.text((80, 158), "tự train được", font=font(58, True), fill=TEAL)
    d.text((82, 236), "6,1M tham số acoustic · 24 kHz · ONNX CPU · một giọng", font=font(23), fill=MUTED)
    # chips
    chips = [("NHỎ", "6,1M"), ("NHANH", "ONNX CPU"), ("TỰ TRAIN", "60k bước")]
    cx = 82
    for label, value in chips:
        tw = int(d.textlength(label, font=font(15, True)) + d.textlength(value, font=font(17, True)) + 34)
        box(d, (cx, 278, cx + tw, 316), (231, 243, 241), radius=10)
        d.text((cx + 12, 286), label, font=font(15, True), fill=TEAL_D)
        d.text((cx + 12 + d.textlength(label, font=font(15, True)) + 8, 284), value, font=font(17, True), fill=TEAL_D)
        cx += tw + 12

    stages = [
        ("01", "VĂN BẢN", "câu tiếng Việt + dấu câu", (238, 244, 245), INK),
        ("02", "FRONTEND ÂM TIẾT", "O · M · N · C + thanh + boundary", (229, 240, 243), INK),
        ("03", "ACOUSTIC v2_slot5", "6,1M · 60k bước · dự đoán mel", (224, 242, 238), TEAL_D),
        ("04", "MEL 100 BIN", "24 kHz · tự ngắt nghỉ", (255, 243, 224), (122, 68, 8)),
        ("05", "VOCOS", "pretrained · mel → phổ", (239, 235, 249), (59, 42, 101)),
        ("06", "WAV 24 kHz", "nghe / tải trên web demo", (231, 246, 237), GREEN),
    ]
    y = 350
    bh, gap = 112, 28
    for index, (num, title, detail, fill, ink) in enumerate(stages):
        top = y + index * (bh + gap)
        box(d, (x0, top, x0 + bw, top + bh), fill, outline=LINE)
        # number pill
        box(d, (x0 + 22, top + 27, x0 + 76, top + 63), WHITE, radius=9)
        d.text((x0 + 37, top + 33), num, font=font(18, True), fill=ink)
        d.text((x0 + 98, top + 22), title, font=font(28, True), fill=ink)
        d.text((x0 + 98, top + 62), detail, font=font(21), fill=(74, 87, 100))
        if index < len(stages) - 1:
            ay = top + bh
            d.line((W // 2, ay + 3, W // 2, ay + gap - 5), fill=(170, 190, 190), width=3)
            d.polygon([(W // 2 - 7, ay + gap - 9), (W // 2 + 7, ay + gap - 9), (W // 2, ay + gap - 1)], fill=(170, 190, 190))
    # output caption side
    d.text((x0 + bw + 26, 350 + 2 * (bh + gap) + 40), "6,1M\ntham số", font=font(18, True), fill=TEAL)
    d.text((x0 + bw + 26, 350 + 3 * (bh + gap) + 40), "alpha\n1.5", font=font(18, True), fill=ORANGE)
    d.text((x0 + bw + 26, 350 + 4 * (bh + gap) + 40), "24 kHz", font=font(18, True), fill=PURPLE)

    # metrics
    d.text((80, 1225), "Tóm tắt bằng số", font=font(26, True), fill=INK)
    metrics = [
        ("19,89 h", "dữ liệu sạch"),
        ("17,9 h", "train"),
        ("5 h 46", "60k bước trên M6"),
        ("4,0 dB", "holdout mel"),
        ("24/24", "A/B tai người"),
        ("0 lỗi", "bất biến dữ liệu"),
    ]
    mw, mh = 320, 72
    mx, my = 80, 1268
    for i, (value, label) in enumerate(metrics):
        col, row = i % 3, i // 3
        x = mx + col * (mw + 30)
        yy = my + row * (mh + 14)
        box(d, (x, yy, x + mw, yy + mh), WHITE, radius=10, outline=LINE)
        d.text((x + 14, yy + 9), value, font=font(26, True), fill=TEAL_D)
        d.text((x + 14, yy + 44), label, font=font(16), fill=MUTED)

    # footer
    d.rectangle((0, 1440, W, H), fill=(19, 44, 47))
    d.text((80, 1448), "CODE MỞ  ·  WEIGHTS RESEARCH  ·  CC-BY-NC-4.0", font=font(16, True), fill=(171, 220, 210))
    d.text((80, 1471), "github.com/dvchd/ViFastTts   ·   vifasttts.hoctuthien.com", font=font(17), fill=(220, 235, 230))
    d.text((820, 1451), "N0  ·  2026", font=font(18, True), fill=(171, 220, 210))

    out = Path("artifacts/ngochuyen/vifasttts_model_flow.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    print(out, out.stat().st_size)


if __name__ == "__main__":
    main()
