"""Đối chiếu frontend Python ↔ Rust bằng dữ liệu sinh tự động.

Chạy từ repo root sau khi build `vifasttts-parse`:

    .venv/bin/python tools/rust_parity.py --matrix --output artifacts/rust_parity

Mục tiêu: so *giá trị* (normalized + 7 ID + parsed), không chỉ shape.
Mặc định dùng profile **live** (không nạp custom_reading local), đúng container.
Thêm `--full-custom` để kiểm profile full.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from vifasttts.frontend.custom_reading import apply_custom_reading
from vifasttts.frontend.normalizer import NormalizerOptions, normalize_text
from vifasttts.frontend.orthography import compose_canonical
from vifasttts.frontend.pipeline import parse_text
from vifasttts.frontend.rules import (
    CODA_ABSTRACT,
    CODA_TONE_COMPATIBILITY,
    MEDIAL_NUCLEUS_COMPATIBILITY,
    NUCLEUS_ABSTRACT,
    ONSET_ABSTRACT,
    SPECIAL_VOWELS,
)
from vifasttts.frontend.syllable import _parse_vowel
from vifasttts.frontend.vocab import ComponentVocabs
from vifasttts.types import Tone

BUILTIN = ROOT / "configs" / "overrides_vi.json"
RUST_BIN = ROOT / "rust" / "target" / "release" / "vifasttts-parse"
if not RUST_BIN.exists():
    RUST_BIN = ROOT / "rust" / "target" / "debug" / "vifasttts-parse"


def live_options() -> NormalizerOptions:
    entries = json.loads(BUILTIN.read_text(encoding="utf-8"))
    phrase = {
        key: value
        for key, value in entries.items()
        if not re.fullmatch(r"[A-Za-zÀ-ỹĐđ]+", key)
    }
    return NormalizerOptions(
        exact_overrides=phrase,
        english_overrides={key.lower(): value for key, value in entries.items()},
    )


def matrix_cases() -> list[str]:
    """Sinh đúng ma trận 49.104 tổ hợp của `tests/test_parser_matrix.py`."""
    words: list[str] = []
    onsets = [onset for onset in ONSET_ABSTRACT if onset]
    vowel_parts = list(NUCLEUS_ABSTRACT) + list(SPECIAL_VOWELS)
    for onset, vowel_part, coda, tone in itertools.product(
        onsets, vowel_parts, list(CODA_ABSTRACT), list(Tone)
    ):
        if tone.value not in CODA_TONE_COMPATIBILITY[CODA_ABSTRACT[coda]]:
            continue
        try:
            medial_s, nucleus_s, medial_a, nucleus_a = _parse_vowel(vowel_part, onset == "qu")
        except ValueError:
            continue
        if nucleus_a not in MEDIAL_NUCLEUS_COMPATIBILITY[medial_a]:
            continue
        words.append(compose_canonical(onset, medial_s, nucleus_s, coda, tone))
    return words


def curated_cases() -> list[str]:
    cases: list[str] = [
        "",
        "   ",
        "Chào bạn, hôm nay trời đẹp quá!",
        "TP.HCM có H2SO4 và x^2, Qualcomm.",
        "Hôm nay 14h30, giá 50.000đ.",
        "AI, API, CPU, VPS và Rust.",
        "quốc quê qua quyển quân",
        "0977123456 và +84977123456",
        "email@abc.com và khongdich.com",
        "ngày 25/12/2023 lúc 14:30",
        "1/2, 3-5, 10-20%, 3,14, -42",
        "5G, 4G, 2+2=4, 3x4, 10÷2",
        "m/s, km/h, 10 m/s², 5 kg, 30°C",
        r"\frac{a}{b}, \sqrt{x}, x^2, H2O, CO2, Fe3+",
        "VNG, COVID-19, XYZ, wav, Zibble Qwux",
        "Hôm nay trời đẹp... nhưng lạnh.",
        "Thử NFD: Chào bạn",
        "CJK: 日本語, Cyrillic: Привет, emoji: 😀",
        "dấu câu: (Chào) [bạn] {nhé}!",
        "TP. HCM, tp. hcm, tp.hcm, TPHCM",
        "v.v., etc, vv, ths, PGS, TS",
    ]

    entries = json.loads(BUILTIN.read_text(encoding="utf-8"))
    for key, value in entries.items():
        cases.append(key)
        cases.append(value)

    from vifasttts.frontend.english_fallback import (
        ACRONYM_READINGS,
        CASE_INSENSITIVE_ENGLISH,
        EXACT_PRODUCT_NAMES,
    )

    cases.extend(ACRONYM_READINGS)
    cases.extend(ACRONYM_READINGS.values())
    cases.extend(CASE_INSENSITIVE_ENGLISH)
    cases.extend(CASE_INSENSITIVE_ENGLISH.values())
    cases.extend(EXACT_PRODUCT_NAMES)
    cases.extend(EXACT_PRODUCT_NAMES.values())
    return [case for case in cases if case]


def build_cases(matrix: bool) -> list[dict]:
    texts = curated_cases()
    if matrix:
        texts.extend(matrix_cases())
    # Bỏ trùng nhưng giữ thứ tự.
    seen: set[str] = set()
    cases: list[dict] = []
    for text in texts:
        if text in seen:
            continue
        seen.add(text)
        cases.append({"text": text, "resolve_oov": True, "live": True})
    return cases


def expected(case: dict, options: NormalizerOptions, vocabs: ComponentVocabs) -> dict:
    text = case["text"]
    # Python mặc định đọc custom_reading local; profile live phải bỏ nó.
    import vifasttts.frontend.pipeline as pipe

    original = pipe.apply_custom_reading
    if case.get("custom_reading"):
        table = case["custom_reading"]
        pipe.apply_custom_reading = lambda value: apply_custom_reading(value, table)
    elif case.get("live"):
        pipe.apply_custom_reading = lambda value: value
    try:
        if case.get("custom_reading"):
            normalized_input = apply_custom_reading(text, case["custom_reading"])
        elif case.get("live"):
            normalized_input = text
        else:
            normalized_input = apply_custom_reading(text, None)
        normalized = normalize_text(normalized_input, options=options)
        items = parse_text(
            text,
            options=options,
            resolve_oov=bool(case.get("resolve_oov")),
        )
    finally:
        pipe.apply_custom_reading = original
    return {
        "normalized": normalized,
        "ids": [vocabs.encode(item) for item in items],
        "parsed": [item.to_dict() for item in items],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", action="store_true", help="thêm 49.104 tổ hợp parser")
    parser.add_argument("--output", default="artifacts/rust_parity")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--fuzz", type=int, default=0, help="sinh thêm N chuỗi ngẫu nhiên (NFC)")
    parser.add_argument("--fuzz-raw", action="store_true", help="giữ nguyên chuỗi fuzz, không NFC")
    parser.add_argument("--fuzz-combining", action="store_true", help="thêm dấu kết hợp rời (adversarial)")
    parser.add_argument("--reuse", action="store_true", help="dùng lại input/expected đã sinh")
    parser.add_argument("--full-custom", action="store_true", help="kiểm profile full với custom_reading local")
    parser.add_argument("--stop", type=int, default=20, help="số mismatch in ra")
    args = parser.parse_args()

    out_dir = ROOT / args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = build_cases(args.matrix)
    if args.full_custom:
        custom_path = ROOT / "data" / "codelung" / "custom_reading.json"
        custom = json.loads(custom_path.read_text(encoding="utf-8"))
        extra = list(custom.keys()) + list(custom.values())
        extra.append("PS và VPS khác nhau; VBA mở In Xờ Pếch")
        for text in extra:
            cases.append({
                "text": text,
                "resolve_oov": True,
                "live": True,
                "custom_reading": custom,
            })
    if args.fuzz:
        rng = random.Random(20261028)
        alphabet = (
            "aăâbcdđeêghiklmnoôơpqrstuưvxy"
            "AĂÂBCCDĐEÊGHIKLMNOÔƠPQRSTUƯVXY"
            "0123456789"
            " .,!?;:-–—/\\$%()[]{}<>+=&@#^_"
            "日本語Привет😀éèë"
        )
        if args.fuzz_combining:
            alphabet += "\u0300\u0301\u0303\u0309\u0323"
        for _ in range(args.fuzz):
            length = rng.randint(0, 60)
            text = "".join(rng.choice(alphabet) for _ in range(length))
            if not args.fuzz_raw:
                text = unicodedata.normalize("NFC", text)
            cases.append({"text": text, "resolve_oov": True, "live": True})
    if args.limit:
        cases = cases[: args.limit]

    options = live_options()
    vocabs = ComponentVocabs.default()
    input_path = out_dir / "input.jsonl"
    output_path = out_dir / "rust.jsonl"
    expected_path = out_dir / "expected.jsonl"
    if not (args.reuse and input_path.exists() and expected_path.exists()):
        with input_path.open("w", encoding="utf-8") as input_file, expected_path.open(
            "w", encoding="utf-8"
        ) as expected_file:
            for case in cases:
                input_file.write(json.dumps(case, ensure_ascii=False) + "\n")
                expected_file.write(
                    json.dumps(expected(case, options, vocabs), ensure_ascii=False) + "\n"
                )
    else:
        cases = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines()]

    if not RUST_BIN.exists():
        raise SystemExit(f"chưa build {RUST_BIN}; chạy cargo build -p vifasttts-parse")
    result = subprocess.run(
        [
            str(RUST_BIN),
            "parse-batch",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if result.returncode != 0:
        print(result.stderr[-4000:], file=sys.stderr)
        return result.returncode

    mismatches = 0
    with output_path.open(encoding="utf-8") as rust_file, expected_path.open(
        encoding="utf-8"
    ) as expected_file:
        for index, (rust_line, expected_line) in enumerate(zip(rust_file, expected_file)):
            rust = json.loads(rust_line)
            want = json.loads(expected_line)
            got_ids = [item["ids"] for item in rust["items"]]
            problems = []
            if rust.get("normalized") != want["normalized"]:
                problems.append(("normalized", want["normalized"], rust.get("normalized")))
            if got_ids != want["ids"]:
                problems.append(("ids", want["ids"], got_ids))
            got_parsed = [item["parsed"] for item in rust["items"]]
            if got_parsed != want["parsed"]:
                problems.append(("parsed", want["parsed"], got_parsed))
            if problems:
                mismatches += 1
                if mismatches <= args.stop:
                    print(f"\nMISMATCH #{mismatches} case={index} text={cases[index]['text']!r}")
                    for kind, expected_value, got_value in problems:
                        print(f"  {kind} expected={expected_value!r}")
                        print(f"  {kind} rust    ={got_value!r}")
    total = len(cases)
    print(f"\nchecked {total} cases, mismatches={mismatches}")
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
