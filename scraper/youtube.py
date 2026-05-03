"""
scraper/youtube.py — Scrape a YouTube channel with NO API key using Scrapling.

How it works:
  1. Load the channel's /videos and /shorts tabs via Scrapling (Chrome impersonation).
  2. Extract the ytInitialData JSON blob embedded in the page HTML.
  3. Recursively walk the renderer tree to collect video IDs + metadata.
  4. Load each video's watch page to get duration, likes, comments.
"""
from __future__ import annotations
import json
import re

from scrapling.fetchers import StealthyFetcher, Fetcher
from tqdm import tqdm

import config
from utils import parse_duration_seconds, is_short, safe_int


def _fetch_html(url: str, stealth: bool = False) -> str:
    if stealth:
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    else:
        page = Fetcher.get(url, stealthy_headers=True, impersonate="chrome")
    return page.content if hasattr(page, "content") else str(page)


def _extract_json_var(html: str, var_name: str) -> dict | None:
    """Extract a JS variable assignment like `var NAME = {...};` from HTML."""
    for pattern in [
        re.compile(rf'var\s+{var_name}\s*=\s*(\{{.*?\}});\s*(?:var|</script>)', re.DOTALL),
        re.compile(rf'{var_name}\s*=\s*(\{{.+?\}})\s*;', re.DOTALL),
    ]:
        m = pattern.search(html)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    return None


def _text(node) -> str:
    if isinstance(node, dict):
        if "simpleText" in node:
            return str(node["simpleText"])
        if "runs" in node:
            return "".join(r.get("text", "") for r in node["runs"])
    return ""


def _iter_renderers(data):
    """Recursively yield any dict that looks like a video renderer."""
    if isinstance(data, dict):
        if "videoId" in data and ("title" in data or "headline" in data):
            yield data
        for v in data.values():
            yield from _iter_renderers(v)
    elif isinstance(data, list):
        for item in data:
            yield from _iter_renderers(item)


def _parse_approx_views(renderer: dict) -> int:
    for key in ("viewCountText", "shortViewCountText"):
        raw = _text(renderer.get(key, {}))
        if raw:
            digits = re.sub(r"[^\d]", "", raw.split()[0])
            if digits:
                return int(digits)
    return 0


def _scrape_tab(channel_url_base: str, tab: str, max_n: int, stealth: bool) -> list[tuple]:
    """
    Scrape one tab (videos or shorts) and return
    [(video_id, title, approx_views, published_text), ...]
    """
    url  = f"{channel_url_base}/{tab}"
    html = _fetch_html(url, stealth=stealth)
    data = _extract_json_var(html, "ytInitialData")
    if not data:
        return []

    results, seen = [], set()
    for r in _iter_renderers(data):
        vid = r.get("videoId", "")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        title  = _text(r.get("title") or r.get("headline") or {})
        views  = _parse_approx_views(r)
        pub    = _text(r.get("publishedTimeText", {}))
        results.append((vid, title, views, pub))
        if len(results) >= max_n:
            break
    return results


def _enrich_from_watch_page(video_id: str, stealth: bool) -> dict:
    """Load a watch page and extract duration, likes, comments, channel title."""
    url  = f"https://www.youtube.com/watch?v={video_id}"
    result: dict = {}
    try:
        html = _fetch_html(url, stealth=stealth)
    except Exception:
        return result

    pr = _extract_json_var(html, "ytInitialPlayerResponse")
    if pr:
        vd = pr.get("videoDetails", {})
        secs = vd.get("lengthSeconds")
        if secs:
            result["duration_seconds"] = int(secs)
        result["channel_title"] = vd.get("author", "")
        thumbs = vd.get("thumbnail", {}).get("thumbnails", [])
        if thumbs:
            result["thumbnail_url"] = thumbs[-1].get("url", "")

    # Likes — stored in accessibility label
    m = re.search(r'"label"\s*:\s*"([\d,]+)\s+like', html)
    if m:
        result["likes"] = int(m.group(1).replace(",", ""))

    # Comments estimate
    m2 = re.search(r'"commentCount"\s*:\s*\{\s*"simpleText"\s*:\s*"([\d,]+)"', html)
    if m2:
        result["comments"] = int(m2.group(1).replace(",", ""))

    return result


def _channel_base_url(identifier: str) -> str:
    if identifier.startswith("UC"):
        return f"https://www.youtube.com/channel/{identifier}"
    if identifier.startswith("@"):
        return f"https://www.youtube.com/{identifier}"
    return f"https://www.youtube.com/@{identifier}"


def scrape_channel(
    channel_identifier: str,
    max_results: int | None = None,
    stealth: bool | None = None,
) -> list[dict]:
    """
    Scrape a YouTube channel without any API key.

    Args:
        channel_identifier: Channel ID (UCxxxx), handle (@Name), or custom name
        max_results: Total videos to return (split between videos + shorts tabs)
        stealth: Use headless browser (slower). Defaults to config.USE_STEALTH.
    """
    if max_results is None:
        max_results = config.MAX_RESULTS_PER_CHANNEL
    if stealth is None:
        stealth = config.USE_STEALTH

    base  = _channel_base_url(channel_identifier)
    half  = max(1, max_results // 2)

    print(f"  → /videos tab")
    videos_raw = _scrape_tab(base, "videos", half, stealth)
    print(f"  → /shorts tab")
    shorts_raw = _scrape_tab(base, "shorts", half, stealth)

    # Deduplicate
    seen, combined = set(), []
    for item in videos_raw + shorts_raw:
        if item[0] not in seen:
            seen.add(item[0])
            combined.append(item)

    if not combined:
        return []

    videos: list[dict] = []
    for vid_id, title, approx_views, pub_text in tqdm(
        combined, desc=f"  Enriching [{channel_identifier[:18]}]", unit="vid"
    ):
        detail       = _enrich_from_watch_page(vid_id, stealth=stealth)
        duration_s   = detail.get("duration_seconds", 0)

        videos.append({
            "video_id":         vid_id,
            "title":            title,
            "published_at":     pub_text,
            "channel_id":       channel_identifier,
            "channel_title":    detail.get("channel_title", ""),
            "duration_seconds": duration_s,
            "is_short":         is_short(duration_s, title),
            "views":            approx_views,
            "likes":            detail.get("likes", 0),
            "comments":         detail.get("comments", 0),
            "thumbnail_url":    detail.get("thumbnail_url", f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"),
            "video_url":        f"https://www.youtube.com/watch?v={vid_id}",
        })

    return videos
