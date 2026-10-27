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


def test_chemical_and_physics_phrases_are_literal():
    options = NormalizerOptions(exact_overrides={
        "H2 + O2 -> H2O": "hát hai cộng ô hai tạo ra nước",
        "x^2": "x bình phương",
        "m/s": "mét trên giây",
    })
    assert normalize_text("H2 + O2 -> H2O", options=options) == "hát hai cộng ô hai tạo ra nước"
    assert normalize_text("x^2", options=options) == "x bình phương"
    assert normalize_text("m/s", options=options) == "mét trên giây"


def test_latex_phrase_is_literal():
    options = NormalizerOptions(exact_overrides={r"\frac{a}{b}": "a trên b"})
    assert normalize_text(r"\frac{a}{b}", options=options) == "a trên b"
