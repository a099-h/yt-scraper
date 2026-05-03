"""
tests/test_helpers.py
"""
import pytest
from utils.helpers import parse_duration_seconds, is_short, safe_int, format_number


def test_parse_duration_seconds():
    assert parse_duration_seconds("PT4M13S") == 253
    assert parse_duration_seconds("PT1H") == 3600
    assert parse_duration_seconds("PT0S") == 0
    assert parse_duration_seconds("GARBAGE") == 0


def test_is_short_by_duration():
    assert is_short(59) is True
    assert is_short(60) is True
    assert is_short(61) is False


def test_is_short_by_hashtag():
    assert is_short(120, title="#Shorts tutorial") is True
    assert is_short(120, title="Normal video") is False


def test_safe_int():
    assert safe_int("12345") == 12345
    assert safe_int(None) == 0
    assert safe_int("") == 0
    assert safe_int(99) == 99


def test_format_number():
    assert format_number(1_500_000) == "1.50M"
    assert format_number(5_000) == "5.0K"
    assert format_number(999) == "999"
