"""
utils/helpers.py — Shared utility functions
"""
from __future__ import annotations
import isodate
import re


def parse_duration_seconds(iso_duration: str) -> int:
    """Convert ISO-8601 duration (PT4M13S) → total seconds."""
    try:
        return int(isodate.parse_duration(iso_duration).total_seconds())
    except Exception:
        return 0


def is_short(duration_seconds: int, title: str = "", description: str = "") -> bool:
    """
    Heuristic: YouTube Shorts are ≤ 60 s OR contain '#Shorts' in metadata.
    """
    if duration_seconds <= 60:
        return True
    text = (title + " " + description).lower()
    return bool(re.search(r"#short", text))


def safe_int(value) -> int:
    """Coerce API string stats to int gracefully."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def format_number(n: int) -> str:
    """Pretty-print large numbers: 1_234_567 → '1.23M'."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)
