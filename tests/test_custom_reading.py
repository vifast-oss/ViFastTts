"""Test cách đọc riêng (custom) — không đụng từ điển chuẩn."""

from __future__ import annotations

from vifasttts.frontend.custom_reading import apply_custom_reading
from vifasttts.frontend.pipeline import parse_text

TABLE = {"vba": "vi be a", "vb": "vi be", "vps": "vi pi ét", "ps": "pi ét", "vs": "vi ét",
            "ch": "xê hát"}


def test_khop_cum_dai_truoc():
    assert apply_custom_reading("Dùng VBA để mở", TABLE) == "Dùng vi be a để mở"
    assert apply_custom_reading("dùng VB", TABLE) == "dùng vi be"


def test_khong_sinh_them_am_tiet():
    out = apply_custom_reading("PS và VPS khác nhau", TABLE)
    assert out == "pi ét và vi pi ét khác nhau"


def test_ranh_gioi_tu():
    assert apply_custom_reading("VPSX", TABLE) == "VPSX"
    assert apply_custom_reading("(VPS)", TABLE) == "(vi pi ét)"


def test_parse_khong_lap_tu():
    """Chuỗi thay KHÔNG lặp; normalizer vẫn tách "es" (âm tiết ngoài hệ Việt) thành 2 âm tiết.

    => ghi nhận hạn chế: muốn "es" đọc đúng 1 âm tiết phải sửa normalizer (chưa làm).
    """
    raw = [s.raw for s in parse_text("PS và VPS khác nhau", resolve_oov=True)]
    assert raw == ["pi", "ét", "và", "vi", "pi", "ét", "khác", "nhau"]


def test_validation_bat_gia_tri_sai():
    """Giá trị parse ra nhiều âm tiết hơn số từ phải báo lỗi, không lặng lẽ tách."""
    import pytest

    from vifasttts.frontend.custom_reading import _validate

    with pytest.raises(ValueError):
        _validate({"ps": "pi es"})


def test_khoa_nhieu_tu():
    """v18.30 (B3): khoá nhiều từ ("in xờ pếch") thay được, ưu tiên khoá dài, không phá từ đơn."""
    table = {"in xờ pếch": "in sờ pếch tờ", "vps": "vi pi ét"}
    assert apply_custom_reading("mở In Xờ Pếch lên", table) == "mở in sờ pếch tờ lên"
    assert apply_custom_reading("VPS và in xờ pếch", table) == "vi pi ét và in sờ pếch tờ"


def test_khoa_nhieu_tu_khong_khop_mot_phan():
    """Không thay khi chỉ khớp một phần cụm (ranh giới từ)."""
    table = {"in xờ pếch": "in sờ pếch tờ"}
    assert apply_custom_reading("in xờ", table) == "in xờ"
