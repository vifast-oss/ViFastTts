"""Unit test chuẩn hoá text dataset ngochuyen (N0)."""

from __future__ import annotations

from tools.nguyen_extract import preprocess_text


def test_fix_leading_zero() -> None:
    assert preprocess_text("trong 02 ngày") == "trong 2 ngày"


def test_fix_date_and_month_year() -> None:
    assert preprocess_text("Ngày 23/4/2024, Cục") == "Ngày 23 tháng 4 năm 2024, Cục"
    assert preprocess_text("tháng 5/2024") == "tháng 5 năm 2024"


def test_no_double_ngay() -> None:
    fixed = preprocess_text("Ngày 01/6/2024")
    assert fixed == "Ngày 1 tháng 6 năm 2024"
    assert "ngày ngày" not in fixed.lower()


def test_arrow_and_range() -> None:
    assert "đến" in preprocess_text("A -> B")
    assert preprocess_text("2020-2021") == "2020 đến 2021"
