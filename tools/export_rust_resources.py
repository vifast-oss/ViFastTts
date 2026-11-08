"""Xuất bảng dữ liệu frontend Python sang JSON cho bản Rust.

Mục đích: Rust và Python dùng **cùng một nguồn** thay vì chép tay từ điển.
Chạy từ repo root:

    .venv/bin/python tools/export_rust_resources.py

Ghi vào `rust/crates/core/domain/text/resources/`. Không chứa model/audio.
"""

from __future__ import annotations

import json
from pathlib import Path

from vifasttts.frontend.english_fallback import (
    ACRONYM_READINGS,
    CASE_INSENSITIVE_ENGLISH,
    EXACT_PRODUCT_NAMES,
)
from vifasttts.frontend.oov import LETTER_READINGS
from vifasttts.frontend.vocab import VOCAB_HASH, VOCAB_VERSION, vocab_payload

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "rust" / "crates" / "core" / "domain" / "text" / "resources"


def _write(name: str, payload: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    vocab = vocab_payload()
    _write("vocab.json", {
        "version": VOCAB_VERSION,
        "hash": VOCAB_HASH,
        **vocab,
    })
    _write("acronyms.json", ACRONYM_READINGS)
    _write("english.json", CASE_INSENSITIVE_ENGLISH)
    _write("products.json", EXACT_PRODUCT_NAMES)
    _write("letter_readings.json", LETTER_READINGS)

    overrides_path = ROOT / "deploy" / "vifasttts_web" / "configs" / "overrides_vi.json"
    _write("overrides_vi.json", json.loads(overrides_path.read_text(encoding="utf-8")))

    # File này chỉ dùng cho profile "full"; production live không nạp mặc định.
    custom_path = ROOT / "data" / "codelung" / "custom_reading.json"
    if custom_path.exists():
        _write("custom_reading.json", json.loads(custom_path.read_text(encoding="utf-8")))
    else:
        _write("custom_reading.json", {})

    _write("frontend_meta.json", {
        "frontend_version": "vi-frontend-v1",
        "vocab_version": VOCAB_VERSION,
        "vocab_hash": VOCAB_HASH,
    })


if __name__ == "__main__":
    main()
