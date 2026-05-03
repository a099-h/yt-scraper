"""
transcript/fetcher.py — Fetch YouTube transcripts using Scrapling (no API key required).

Strategy:
  1. Use Scrapling's Fetcher (or StealthyFetcher) to load the YouTube watch page.
  2. Parse the ytInitialPlayerResponse JSON blob embedded in the page <script> tags.
  3. Extract the timedtext/caption track URL from the playerCaptionsTracklistRenderer.
  4. Fetch that XML caption track URL and parse the <text> segments.

No YouTube Data API key. No third-party caption library. Zero quota usage.
"""
from __future__ import annotations
import json
import re
from xml.etree import ElementTree

from scrapling.fetchers import StealthyFetcher, Fetcher


# ── Internals ──────────────────────────────────────────────────────────────────

def _extract_player_response(page_html: str) -> dict | None:
    """
    Pull the ytInitialPlayerResponse JSON object out of raw page HTML.
    YouTube embeds this as a JS variable assignment in a <script> tag.
    """
    pattern = re.compile(
        r'var\s+ytInitialPlayerResponse\s*=\s*(\{.*?\});\s*(?:var|</script>)',
        re.DOTALL,
    )
    match = pattern.search(page_html)
    if not match:
        pattern2 = re.compile(r'ytInitialPlayerResponse\s*=\s*(\{.+?\})\s*;', re.DOTALL)
        match = pattern2.search(page_html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _get_caption_track_url(player_response: dict, lang: str = "en") -> str | None:
    """
    Navigate the player response JSON to find a caption track URL.
    Prefers manual captions, falls back to auto-generated (asr) ones.
    """
    try:
        tracks = (
            player_response
            ["captions"]
            ["playerCaptionsTracklistRenderer"]
            ["captionTracks"]
        )
    except (KeyError, TypeError):
        return None

    if not tracks:
        return None

    preferred = None
    asr_fallback = None

    for track in tracks:
        base_url = track.get("baseUrl", "")
        lang_code = track.get("languageCode", "")
        kind = track.get("kind", "")   # "asr" = auto-generated

        if lang_code.startswith(lang):
            if kind != "asr" and preferred is None:
                preferred = base_url
            elif kind == "asr" and asr_fallback is None:
                asr_fallback = base_url

    return preferred or asr_fallback or tracks[0].get("baseUrl")


def _parse_caption_xml(xml_text: str) -> str:
    """
    Parse the timed-text XML YouTube returns for caption tracks.
    Format: <transcript><text start="..." dur="...">caption text</text>...</transcript>
    """
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return ""

    parts = []
    for elem in root.iter("text"):
        raw = elem.text or ""
        raw = (
            raw.replace("&#39;", "'")
               .replace("&amp;", "&")
               .replace("&quot;", '"')
               .replace("&lt;", "<")
               .replace("&gt;", ">")
               .strip()
        )
        if raw:
            parts.append(raw)

    return " ".join(parts)


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_transcript(
    video_id: str,
    languages: list[str] | None = None,
    use_stealth: bool = False,
) -> str | None:
    """
    Fetch the transcript for a YouTube video — no API key needed.

    Uses Scrapling to load the watch page, extracts the embedded player
    response JSON, resolves the caption track URL, then downloads and
    parses the XML caption track.

    Args:
        video_id:    YouTube video ID (e.g. 'dQw4w9WgXcQ')
        languages:   Preferred language codes in priority order (default: ['en'])
        use_stealth: Use StealthyFetcher (bypasses bot detection, slower/heavier)
                     vs plain Fetcher (faster, usually enough for YouTube).

    Returns:
        Full transcript as a single string, or None if unavailable.
    """
    if languages is None:
        languages = ["en"]

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        if use_stealth:
            page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
        else:
            page = Fetcher.get(url, stealthy_headers=True, impersonate="chrome")

        raw_html = page.content if hasattr(page, "content") else str(page)
    except Exception:
        return None

    player_response = _extract_player_response(raw_html)
    if not player_response:
        return None

    caption_url = None
    for lang in languages:
        caption_url = _get_caption_track_url(player_response, lang)
        if caption_url:
            break

    if not caption_url:
        return None

    if caption_url.startswith("//"):
        caption_url = "https:" + caption_url

    try:
        caption_page = Fetcher.get(caption_url, stealthy_headers=True, impersonate="chrome")
        xml_text = caption_page.content if hasattr(caption_page, "content") else str(caption_page)
        return _parse_caption_xml(xml_text) or None
    except Exception:
        return None


def fetch_transcripts_bulk(
    videos: list[dict],
    languages: list[str] | None = None,
    use_stealth: bool = False,
) -> list[dict]:
    """
    Enrich a list of video dicts (from the scraper) with a 'transcript' key.
    Mutates the list in-place and also returns it for chaining.
    """
    for video in videos:
        video["transcript"] = fetch_transcript(
            video["video_id"],
            languages=languages,
            use_stealth=use_stealth,
        )
    return videos
