"""Kiểm từ điển override công khai: sạch alias ASR + viết tắt thường gặp."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from vifasttts.frontend.normalizer import NormalizerOptions, normalize_text
from vifasttts.frontend.syllable import safe_parse_syllable

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "configs" / "overrides_vi.json"
DEPLOY_OVERRIDES = ROOT / "deploy" / "vifasttts_web" / "configs" / "overrides_vi.json"


def _load() -> dict[str, str]:
    return json.loads(OVERRIDES.read_text(encoding="utf-8"))


def _options() -> NormalizerOptions:
    entries = _load()
    phrase_keys = {
        key: value for key, value in entries.items()
        if not re.fullmatch(r"[A-Za-zÀ-ỹĐđ]+", key)
    }
    return NormalizerOptions(
        exact_overrides=phrase_keys,
        english_overrides=entries,
    )


def test_deploy_copy_matches_source():
    assert DEPLOY_OVERRIDES.read_text(encoding="utf-8") == OVERRIDES.read_text(encoding="utf-8")


def test_moi_cach_doc_parse_duoc():
    for key, reading in _load().items():
        assert key.strip() and reading.strip()
        for word in reading.split():
            assert safe_parse_syllable(word) is not None, f"{word!r} trong {key!r}"


def test_khong_con_alias_asr_va_key_nguy_hiem():
    entries = _load()
    for bad in ("dipsic", "dipick", "dipix", "analyer", "antiravity", "appile", "cching"):
        assert bad not in entries
    # Key một chữ cái dễ đè lên chữ cái bình thường trong câu.
    assert not [key for key in entries if len(key) == 1]


@pytest.mark.parametrize("text,expected", [
    ("TP.HCM", "thành phố hồ chí minh"),
    ("tp. HCM", "thành phố hồ chí minh"),
    ("v.v.", "vân vân"),
    ("hugging face", "hắc ghinh phây"),
    ("DeepSeek", "đíp sích"),
    ("UBND", "ủy ban nhân dân"),
    ("HĐND", "hội đồng nhân dân"),
    ("VTV", "vê tê vê"),
    ("HN", "hà nội"),
    ("BD", "bình dương"),
    ("ĐN", "đà nẵng"),
    ("TƯ", "trung ương"),
    ("QL", "quốc lộ"),
    ("CĐ", "cao đẳng"),
    ("GD&ĐT", "giáo dục và đào tạo"),
    ("HS-SV", "học sinh và sinh viên"),
    ("B công an", "bộ công an"),
    ("TBYT", "thiết bị y tế"),
    ("BV", "bệnh viện"),
    ("TNHH", "trách nhiệm hữu hạn"),
    ("CP", "cổ phần"),
    ("DN", "doanh nghiệp"),
    ("DNTN", "doanh nghiệp tư nhân"),
    ("CK", "chuyển khoản"),
    ("VAT", "thuế giá trị gia tăng"),
    ("ĐKKD", "đăng ký kinh doanh"),
    ("BĐS", "bất động sản"),
    ("Ngân hàng TMCP", "ngân hàng thương mại cổ phần"),
    ("VP", "văn phòng"),
    ("protein", "pờ rô tê in"),
    ("apple", "áp pồ"),
    ("khongdich", "không dịch"),
    ("smartphone", "sờ mát phôn"),
    ("bug", "bắc"),
    ("download", "đao lốt"),
    ("windows", "uyn đâu"),
    ("Qualcomm", "quan com"),
    ("H2SO4", "hát hai ét ô bốn"),
    ("x^2", "ích bình phương"),
    ("CO2", "xê ô hai"),
    ("google.com", "gu gồ chấm com"),
    ("khongdich.com", "không dịch chấm com"),
    ("hiđro", "hi đờ rô"),
])
def test_viet_tat_va_tu_thong_dung(text, expected):
    assert normalize_text(text, options=_options()) == expected


def test_viet_tat_lowercase_van_khop():
    options = _options()
    assert normalize_text("ubnd", options=options) == "ủy ban nhân dân"
    assert normalize_text("hđnd", options=options) == "hội đồng nhân dân"


def test_email_local_part_known_va_lạ():
    assert normalize_text("khongdich@gmail.com") == "không dịch a còng giê meo chấm com"
    # Username lạ phải được đánh vần, không bỏ mất local part.
    unknown = normalize_text("nguyenvana@yahoo.com")
    assert "en giê" in unknown
    assert "a còng" in unknown
    assert normalize_text("abc123@gmail.com").startswith("a bê xê một hai ba a còng")
