"""
transcript/fetcher.py — Fetch YouTube transcripts without an API key.

Strategy (tried in order):
  1. requests + YouTube's internal timedtext API  ← no extra dep, very fast
  2. yt-dlp subtitle download                     ← fallback if yt-dlp is installed

The requests path scrapes the initial page data to discover the caption track
URL, then fetches the XML transcript directly — the same endpoint YouTube's
own player uses.  No API key, no authentication.
"""
from __future__ import annotations

import html
import json
import os
import re
import xml.etree.ElementTree as ET
from typing import Optional

import requests


# ── shared session ─────────────────────────────────────────────────────────────

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        # Bypass the GDPR/cookie consent gate
        "Cookie": "CONSENT=YES+cb.20210328-17-p0.en+FX+353; YSC=random123",
    }
)


# ── Strategy 1: requests ───────────────────────────────────────────────────────

def _fetch_via_requests(video_id: str, languages: list) -> Optional[str]:
    """
    Fetch transcript by:
      1. Loading the watch page to extract the caption track list JSON.
      2. Picking the best language match.
      3. Fetching the XML timedtext URL directly.
      4. Parsing the XML into plain text.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        resp = _SESSION.get(url, timeout=20)
        resp.raise_for_status()
    except Exception:
        return None

    page = resp.text

    # YouTube embeds caption track info inside the page JS.
    # Try to find captionTracks array directly
    m = re.search(r'"captionTracks"\s*:\s*(\[.*?\])', page, re.DOTALL)
    if m:
        try:
            tracks = json.loads(m.group(1))
        except Exception:
            tracks = []
    else:
        # Try the full captions blob
        m2 = re.search(
            r'"captions"\s*:\s*(\{"playerCaptionsTracklistRenderer".*?\})\s*,\s*"videoDetails"',
            page, re.DOTALL,
        )
        if m2:
            try:
                blob = json.loads(m2.group(1))
                tracks = (
                    blob
                    .get("playerCaptionsTracklistRenderer", {})
                    .get("captionTracks", [])
                )
            except Exception:
                tracks = []
        else:
            return None

    if not tracks:
        return None

    chosen = _pick_track(tracks, languages)
    if not chosen:
        return None

    base_url = chosen.get("baseUrl", "")
    if not base_url:
        return None

    # Request XML format (most reliable)
    xml_url = base_url if "fmt=" in base_url else base_url + "&fmt=xml"
    try:
        r2 = _SESSION.get(xml_url, timeout=15)
        r2.raise_for_status()
    except Exception:
        return None

    return _parse_xml_transcript(r2.text)


def _pick_track(tracks: list, languages: list) -> Optional[dict]:
    """
    Choose the caption track that best matches the requested languages.
    Prefers manual captions; falls back to auto-generated (ASR).
    """
    by_lang: dict = {}
    for t in tracks:
        lc = t.get("languageCode", "")
        by_lang.setdefault(lc, []).append(t)

    for lang in languages:
        candidates = by_lang.get(lang, [])
        if not candidates:
            # Prefix match (e.g. 'en' matches 'en-US')
            candidates = [t for lc, tl in by_lang.items() if lc.startswith(lang) for t in tl]
        if candidates:
            manual = [t for t in candidates if t.get("kind") != "asr"]
            return manual[0] if manual else candidates[0]

    # Fallback: first available track
    return tracks[0] if tracks else None


def _parse_xml_transcript(xml_text: str) -> Optional[str]:
    """
    Parse YouTube's timedtext XML into clean plain text.

    Format:
      <transcript>
        <text start="0.5" dur="1.2">Hello world</text>
        ...
      </transcript>
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    parts: list = []
    prev = ""
    for elem in root.iter("text"):
        raw = elem.text or ""
        text = html.unescape(raw).strip()
        text = re.sub(r"<[^>]+>", "", text).strip()
        if not text:
            continue
        # Skip only CONSECUTIVE duplicates (auto-caption artefact)
        if text == prev:
            continue
        prev = text
        parts.append(text)

    return " ".join(parts) if parts else None


# ── Strategy 2: yt-dlp (fallback) ─────────────────────────────────────────────

def _fetch_via_ytdlp(video_id: str, languages: list) -> Optional[str]:
    """Download transcript using yt-dlp if installed."""
    try:
        import yt_dlp  # noqa
    except ImportError:
        return None

    import glob
    import tempfile

    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_template = os.path.join(tmpdir, "%(id)s.%(ext)s")
        ydl_opts = {
            "skip_download":     True,
            "writesubtitles":    True,
            "writeautomaticsub": True,
            "subtitleslangs":    languages,
            "subtitlesformat":   "vtt",
            "outtmpl":           out_template,
            "quiet":             True,
            "no_warnings":       True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception:
            return None

        vtt_files = glob.glob(os.path.join(tmpdir, "*.vtt"))
        if not vtt_files:
            return None

        return _parse_vtt(vtt_files[0])


def _parse_vtt(path: str) -> Optional[str]:
    """Parse a WebVTT subtitle file into clean plain text."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return None

    lines: list = []
    prev = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        if "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line:
            continue
        # Only skip CONSECUTIVE duplicates — not global ones (original bug fix)
        if line == prev:
            continue
        prev = line
        lines.append(line)

    return " ".join(lines) if lines else None


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_transcript(
    video_id: str,
    languages=None,
) -> Optional[str]:
    """
    Fetch the transcript for a YouTube video as plain text.

    Tries two strategies in order:
      1. Direct HTTP to YouTube's timedtext API (no extra deps, fastest)
      2. yt-dlp subtitle download (if yt-dlp is installed)

    Args:
        video_id:  YouTube video ID (e.g. 'dQw4w9WgXcQ')
        languages: Language codes in priority order (default: ['en'])

    Returns:
        Full transcript as a single string, or None if unavailable.
    """
    if languages is None:
        languages = ["en"]

    result = _fetch_via_requests(video_id, languages)
    if result:
        return result

    return _fetch_via_ytdlp(video_id, languages)


def fetch_transcripts_bulk(
    videos: list,
    languages=None,
) -> list:
    """Enrich a list of video dicts with a 'transcript' key."""
    for video in videos:
        video["transcript"] = fetch_transcript(video["video_id"], languages)
    return videos
