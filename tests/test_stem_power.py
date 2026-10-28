import pytest

from vifasttts.frontend.normalizer import integer_to_words, normalize_text
from vifasttts.frontend.stem import normalize_stem


@pytest.mark.parametrize("source,expected", [
    ("a^2", "a bình phương"),
    ("a^3", "a lập phương"),
    ("b^2", "bê bình phương"),
    ("x^2", "ích bình phương"),
    ("x^3", "ích lập phương"),
    ("x^4", "ích mũ bốn"),
    ("2^3", "hai mũ ba"),
    ("10^2", "mười mũ hai"),
    ("x^{n+1}", "ích mũ en cộng một"),
    ("x^{-1}", "ích mũ trừ một"),
    ("a^{2}", "a bình phương"),
    ("a^2 + b^2", "a bình phương + bê bình phương"),
])
def test_bare_power(source, expected):
    assert normalize_text(source) == expected


def test_bare_power_uses_variable_reading():
    # Đọc tên biến như math mode, không để \"x\" trần cho fallback.
    assert normalize_stem("x^2", lambda n: integer_to_words(n, "north")) == "ích bình phương"


def test_bare_power_keeps_units_and_math_mode():
    # Đơn vị và math mode phải chạy trước, không bị đổi thành "m/s bình phương".
    assert normalize_text("m/s^2") == "mét trên giây bình phương"
    assert normalize_text("3 m^2") == "ba mét bình phương"
    assert normalize_text("$a^2$") == "a mũ hai"


def test_bare_power_does_not_touch_other_carets():
    # Trang trí, C++, điện tích hoá học, cm², số thập phân, chữ dính sau.
    assert normalize_text("^_^") == "^_^"
    assert normalize_text("C++") == "C++"
    assert "bình phương" not in normalize_text("Ca^2+")
    assert "bình phương" not in normalize_text("cm^2")
    assert "bình phương" not in normalize_text("x^2.5")
    assert normalize_text("x^2y") == "x^2y"
