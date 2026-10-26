"""N0 — trích dataset `pnnbao-ump/ngochuyen_voice` từ parquet ra WAV + metadata.

- Ghi WAV **nguyên byte** (PCM 24 kHz mono) — không re-encode, không đổi mẫu.
- Đo chất lượng: duration, peak, RMS, lặng đầu/đuôi, silence ratio, clipping, DC.
- Chuẩn hoá văn bản **trước** khi parse: sửa ngày/giờ, số 0 đứng đầu, mũi tên.
- Không ghi đè dữ liệu cũ; chỉ ghi vào `data/ngochuyen/`.

Chạy:
    .venv/bin/python tools/nguyen_extract.py
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from vifasttts.frontend.pipeline import parse_text
from vifasttts.types import ParseStatus

SR = 24000
HOP = 256
FRAME_MS = 20
SILENCE_DB = -45.0


def preprocess_text(text: str) -> str:
    """Sửa các dạng số/ngày mà frontend đọc sai (đã đo trên mẫu)."""
    text = text.replace("\u200b", " ").replace("\ufeff", " ")
    # Ngày/tháng/năm và tháng/năm trước khi parse (frontend đọc d/m là "phần").
    # Giữ "ngày" đã có sẵn, tránh "Ngày ngày ...".
    text = re.sub(r"(?i)(ngày\s+)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)",
                  lambda m: f"{m.group(1)}{m.group(2)} tháng {m.group(3)} năm {m.group(4)}", text)
    text = re.sub(r"(?i)(tháng\s+)(\d{1,2})/(\d{4})(?!\d)",
                  lambda m: f"{m.group(1)}{m.group(2)} năm {m.group(3)}", text)
    text = re.sub(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)",
                  r"ngày \1 tháng \2 năm \3", text)
    text = re.sub(r"(?<!\d)(\d{1,2})/(\d{4})(?!\d)", r"tháng \1 năm \2", text)
    text = re.sub(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)",
                  r"ngày \1 tháng \2", text)
    # Khoảng số: 2020-2021 → 2020 đến 2021.
    text = re.sub(r"(?<=\d)\s*[-–—]\s*(?=\d)", " đến ", text)
    # Số 0 đứng đầu: 02 → 2, 01 → 1 (frontend đang đọc "không hai").
    text = re.sub(r"\b0+(\d)\b", r"\1", text)
    text = text.replace("->", " đến ").replace("=>", " đến ")
    return re.sub(r"\s+", " ", text).strip()


def audio_stats(wave: np.ndarray, sr: int) -> dict:
    """Thống kê năng lượng / lặng / clipping."""
    width = int(sr * FRAME_MS / 1000)
    if wave.size < width:
        return {"peak": 0.0, "rms_db": -120.0, "silence_ratio": 1.0,
                "lead_silence_s": 0.0, "tail_silence_s": 0.0, "clip_ratio": 0.0,
                "dc_offset": 0.0}
    usable = wave[: wave.size // width * width].reshape(-1, width)
    rms = np.sqrt(np.mean(usable.astype(np.float64) ** 2, axis=1) + 1e-12)
    db = 20.0 * np.log10(rms + 1e-12)
    silent = db < SILENCE_DB
    lead = 0
    while lead < silent.size and silent[lead]:
        lead += 1
    tail = 0
    while tail < silent.size and silent[silent.size - 1 - tail]:
        tail += 1
    peak = float(np.max(np.abs(wave)))
    return {
        "peak": round(peak, 5),
        "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(wave.astype(np.float64) ** 2)) + 1e-12)), 2),
        "silence_ratio": round(float(silent.mean()), 4),
        "lead_silence_s": round(lead * FRAME_MS / 1000, 3),
        "tail_silence_s": round(tail * FRAME_MS / 1000, 3),
        "clip_ratio": round(float(np.mean(np.abs(wave) >= 0.999)), 7),
        "dc_offset": round(float(np.mean(wave)), 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet-dir", default="data/ngochuyen/parquet")
    parser.add_argument("--out-dir", default="data/ngochuyen")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    out = Path(args.out_dir)
    (out / "audio").mkdir(parents=True, exist_ok=True)
    files = sorted(Path(args.parquet_dir).glob("train-*.parquet"))
    if not files:
        raise SystemExit("không có parquet")
    meta_path = out / "meta_raw.jsonl"
    done = 0
    seen: dict[str, str] = {}
    with meta_path.open("w", encoding="utf-8") as handle:
        for parquet in files:
            pf = pq.ParquetFile(parquet)
            for batch in pf.iter_batches(batch_size=64):
                for row in batch.to_pylist():
                    if args.limit and done >= args.limit:
                        break
                    raw = row["audio"]["bytes"]
                    name = Path(row["file_name"]).name
                    wav_path = out / "audio" / name
                    wave, sr = sf.read(io.BytesIO(raw), dtype="float32")
                    if sr != SR or wave.ndim != 1:
                        raise RuntimeError(f"{name}: sr={sr} shape={wave.shape}")
                    if not wav_path.exists() or wav_path.stat().st_size != len(raw):
                        wav_path.write_bytes(raw)
                    sha = hashlib.sha256(raw).hexdigest()
                    text = str(row["transcription"]).strip()
                    text_fixed = preprocess_text(text)
                    try:
                        syllables = parse_text(text_fixed)
                        normalized = " ".join(s.normalized for s in syllables)
                        statuses = [str(s.status) for s in syllables]
                        n_bad = sum(s.status != ParseStatus.VALID for s in syllables)
                        n_fallback = sum(s.status == ParseStatus.FALLBACK_REQUIRED for s in syllables)
                    except Exception as exc:  # noqa: BLE001
                        syllables = []
                        normalized = ""
                        statuses = []
                        n_bad = n_fallback = -1
                        print(f"[warn] parse {name}: {exc}", file=sys.stderr)
                    stats = audio_stats(wave, sr)
                    duration = len(wave) / sr
                    entry = {
                        "id": name.replace(".wav", ""),
                        "file_name": row["file_name"],
                        "wav": str(wav_path),
                        "shard": parquet.name,
                        "audio_sha256": sha,
                        "duration": round(duration, 4),
                        "sr": sr,
                        "samples": int(wave.size),
                        "text_raw": text,
                        "text_fixed": text_fixed,
                        "text_norm": normalized,
                        "n_syllables": len(syllables),
                        "parse_statuses": statuses,
                        "n_bad": n_bad,
                        "n_fallback": n_fallback,
                        "speech_rate": round(len(syllables) / duration, 3) if duration > 0 else 0,
                        "has_digit": bool(re.search(r"\d", text)),
                        "has_date": bool(re.search(r"\d{1,2}/\d{1,2}", text)),
                        "has_leading_zero": bool(re.search(r"\b0\d", text)),
                        "has_arrow": "->" in text or "=>" in text,
                        "has_mixed_alnum": bool(re.search(r"[A-Za-z]\d|\d[A-Za-z]", text)),
                        **stats,
                    }
                    if sha in seen:
                        entry["duplicate_of"] = seen[sha]
                    else:
                        seen[sha] = entry["id"]
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    done += 1
                    if done % 500 == 0:
                        print(json.dumps({"done": done}), flush=True)
                if args.limit and done >= args.limit:
                    break
            if args.limit and done >= args.limit:
                break
    print(json.dumps({"done": done, "meta": str(meta_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
