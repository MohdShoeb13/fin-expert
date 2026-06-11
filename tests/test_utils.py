"""Unit tests for validators and disclaimer helpers."""

import pytest

from src.utils.disclaimers import EDUCATIONAL_DISCLAIMER, with_disclaimer
from src.utils.validators import clamp, normalize_ticker, validate_positive


class TestNormalizeTicker:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("aapl", "AAPL"),
            ("  vti ", "VTI"),
            ("BRK.B", "BRK.B"),
            ("BTC-USD", "BTC-USD"),
            ("A", "A"),
        ],
    )
    def test_valid(self, raw, expected):
        assert normalize_ticker(raw) == expected

    @pytest.mark.parametrize("raw", ["", "  ", "123", "$AAPL", "DROP TABLE", "TOOLONGTICKER"])
    def test_invalid_raises(self, raw):
        with pytest.raises(ValueError, match="Invalid ticker"):
            normalize_ticker(raw)


class TestValidatePositive:
    def test_valid(self):
        assert validate_positive(5, "shares") == 5.0

    @pytest.mark.parametrize("value", [0, -1, None])
    def test_invalid(self, value):
        with pytest.raises(ValueError, match="shares"):
            validate_positive(value, "shares")


def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-5, 0, 10) == 0
    assert clamp(15, 0, 10) == 10


class TestDisclaimer:
    def test_appended(self):
        out = with_disclaimer("Stocks are ownership shares.")
        assert out.startswith("Stocks are ownership shares.")
        assert EDUCATIONAL_DISCLAIMER in out

    def test_idempotent(self):
        once = with_disclaimer("hello")
        twice = with_disclaimer(once)
        assert twice == once
        assert twice.count(EDUCATIONAL_DISCLAIMER) == 1
