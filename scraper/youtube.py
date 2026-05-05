"""
scraper/youtube.py — Scrape a YouTube channel using yt-dlp. No API key needed.

Uses yt-dlp's flat playlist extraction to list videos from /videos and /shorts
tabs, then fetches per-video metadata (duration, likes, comments, thumbnail)
from the same tool — no browser, no scrapling, no playwright.
"""
from __future__ import annotations

import yt_dlp
from tqdm import tqdm

import config
from utils import is_short, safe_int


# ── Silence yt-dlp output ────────────────────────────────────────────────────

class _QuietLogger:
    def debug(self, msg):   pass
    def info(self, msg):    pass
    def warning(self, msg): pass
    def error(self, msg):   pass


_BASE_OPTS = {
    "quiet":       True,
    "no_warnings": True,
    "logger":      _QuietLogger(),
}


# ── Channel URL helper ────────────────────────────────────────────────────────

def _channel_base_url(identifier: str) -> str:
    if identifier.startswith("UC"):
        return f"https://www.youtube.com/channel/{identifier}"
    if identifier.startswith("@"):
        return f"https://www.youtube.com/{identifier}"
    return f"https://www.youtube.com/@{identifier}"


# ── Flat-playlist extraction ──────────────────────────────────────────────────

def _scrape_tab(channel_url_base: str, tab: str, max_n: int) -> list[dict]:
    """
    Use yt-dlp's flat playlist mode to list video IDs + basic metadata
    from a channel tab without downloading anything.
    """
    url = f"{channel_url_base}/{tab}"
    opts = {
        **_BASE_OPTS,
        "extract_flat": "in_playlist",
        "playlistend":  max_n,
        "ignoreerrors": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return []

    if not info or "entries" not in info:
        return []

    results = []
    for entry in (info["entries"] or []):
        if not entry:
            continue
        vid_id = entry.get("id") or entry.get("url", "").split("v=")[-1]
        if not vid_id or len(vid_id) != 11:
            continue
        results.append({
            "video_id":     vid_id,
            "title":        entry.get("title", ""),
            "views":        safe_int(entry.get("view_count") or entry.get("viewCount", 0)),
            "published_at": entry.get("upload_date") or entry.get("publishedTimeText", ""),
        })
        if len(results) >= max_n:
            break
    return results


# ── Per-video enrichment ──────────────────────────────────────────────────────

def _enrich(video_id: str) -> dict:
    """
    Fetch full metadata for a single video using yt-dlp (no download).
    Returns duration, likes, comments, channel_title, thumbnail_url.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    opts = {
        **_BASE_OPTS,
        "skip_download": True,
        "ignoreerrors":  True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return {}

    if not info:
        return {}

    thumbs = info.get("thumbnails") or []
    thumb_url = thumbs[-1]["url"] if thumbs else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    return {
        "channel_title":    info.get("uploader") or info.get("channel", ""),
        "duration_seconds": safe_int(info.get("duration", 0)),
        "views":            safe_int(info.get("view_count", 0)),
        "likes":            safe_int(info.get("like_count", 0)),
        "comments":         safe_int(info.get("comment_count", 0)),
        "thumbnail_url":    thumb_url,
        "published_at":     info.get("upload_date", ""),
        "description":      info.get("description", "") or "",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_channel(
    channel_identifier: str,
    max_results: int | None = None,
    stealth: bool | None = None,   # kept for CLI compatibility, ignored
) -> list[dict]:
    """
    Scrape a YouTube channel without any API key using yt-dlp.

    Args:
        channel_identifier: Channel ID (UCxxxx), handle (@Name), or custom name.
        max_results:        Total videos to return (split between /videos + /shorts).
        stealth:            Ignored (kept for CLI argument compatibility).
    """
    if max_results is None:
        max_results = config.MAX_RESULTS_PER_CHANNEL

    base = _channel_base_url(channel_identifier)
    half = max(1, max_results // 2)

    print("  → /videos tab")
    videos_raw = _scrape_tab(base, "videos", half)
    print("  → /shorts tab")
    shorts_raw = _scrape_tab(base, "shorts", half)

    # Deduplicate across tabs
    seen, combined = set(), []
    for item in videos_raw + shorts_raw:
        if item["video_id"] not in seen:
            seen.add(item["video_id"])
            combined.append(item)

    if not combined:
        return []

    videos: list[dict] = []
    for item in tqdm(combined, desc=f"  Enriching [{channel_identifier[:18]}]", unit="vid"):
        vid_id = item["video_id"]
        detail = _enrich(vid_id)

        duration_s = detail.get("duration_seconds", 0)
        title      = item["title"] or detail.get("title", "")

        videos.append({
            "video_id":         vid_id,
            "title":            title,
            "published_at":     detail.get("published_at") or item.get("published_at", ""),
            "channel_id":       channel_identifier,
            "channel_title":    detail.get("channel_title", ""),
            "duration_seconds": duration_s,
            "is_short":         is_short(duration_s, title),
            "views":            detail.get("views") or item.get("views", 0),
            "likes":            detail.get("likes", 0),
            "comments":         detail.get("comments", 0),
            "thumbnail_url":    detail.get("thumbnail_url",
                                    f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"),
            "video_url":        f"https://www.youtube.com/watch?v={vid_id}",
            "description":      detail.get("description", ""),
        })

    return videos
