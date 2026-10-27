"""Override cụm/domain có dấu chấm phải khớp trước khi tách token."""
from __future__ import annotations

from vifasttts.frontend.normalizer import NormalizerOptions, normalize_text
from vifasttts.frontend.pipeline import parse_text


def _options() -> NormalizerOptions:
    return NormalizerOptions(exact_overrides={
        "khongdich.com": "không dịch chấm com",
        "TP.HCM": "thành phố hồ chí minh",
    })


def test_domain_override_matches_whole_phrase():
    assert normalize_text("Xem tại khongdich.com nhé", options=_options()) == (
        "Xem tại không dịch chấm com nhé"
    )
    items = parse_text("Xem tại khongdich.com nhé", options=_options())
    assert [item.normalized for item in items] == [
        "xem", "tại", "không", "dịch", "chấm", "com", "nhé",
    ]
    assert all(item.status.value == "VALID" for item in items)


def test_domain_override_inside_url_and_case_insensitive():
    got = normalize_text("https://KhongDich.com", options=_options())
    assert got == "hát tê tê pi ét://không dịch chấm com"


def test_phrase_override_with_space_and_dots():
    assert normalize_text("TP.HCM", options=_options()) == "thành phố hồ chí minh"
    assert normalize_text("tp.hcm", options=_options()) == "thành phố hồ chí minh"


def test_unmatched_domain_stays_fallback_not_crash():
    items = parse_text("qwertyzzz.com", options=_options())
    assert len(items) == 2
    assert items[0].status.value == "FALLBACK_REQUIRED"
