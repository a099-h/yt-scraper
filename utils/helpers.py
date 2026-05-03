from __future__ import annotations
import re


def parse_duration_seconds(val) -> int:
    """Accept seconds (int/str) or ISO-8601 string like PT4M13S."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    # ISO-8601
    m = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', s)
    if m:
        h, mn, sc = (int(x or 0) for x in m.groups())
        return h * 3600 + mn * 60 + sc
    # Plain seconds string
    try:
        return int(s)
    except ValueError:
        return 0


def is_short(duration_seconds: int, title: str = "") -> bool:
    if duration_seconds and duration_seconds <= 60:
        return True
    return bool(re.search(r'#short', title, re.IGNORECASE))


def safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)
