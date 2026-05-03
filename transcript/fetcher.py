"""
transcript/fetcher.py — Fetch YouTube transcripts using yt-dlp. No API key required.

yt-dlp downloads the subtitle/caption track directly from YouTube's CDN,
the same way it downloads videos — no API, no authentication.
"""
from __future__ import annotations
import os
import glob
import tempfile

import yt_dlp


def fetch_transcript(
    video_id: str,
    languages: list[str] | None = None,
) -> str | None:
    """
    Download and return the transcript for a YouTube video as plain text.

    Uses yt-dlp to grab auto-generated or manual subtitles.
    No API key. No browser. Very fast.

    Args:
        video_id:  YouTube video ID (e.g. 'dQw4w9WgXcQ')
        languages: Language codes in priority order (default: ['en'])

    Returns:
        Full transcript as a single string, or None if unavailable.
    """
    if languages is None:
        languages = ["en"]

    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_template = os.path.join(tmpdir, "%(id)s.%(ext)s")

        ydl_opts = {
            "skip_download":        True,       # Don't download the video
            "writesubtitles":       True,       # Manual captions
            "writeautomaticsub":    True,       # Auto-generated captions (fallback)
            "subtitleslangs":       languages,
            "subtitlesformat":      "vtt",      # WebVTT — easy to parse
            "outtmpl":              out_template,
            "quiet":                True,
            "no_warnings":          True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception:
            return None

        # Find any .vtt file written
        vtt_files = glob.glob(os.path.join(tmpdir, "*.vtt"))
        if not vtt_files:
            return None

        return _parse_vtt(vtt_files[0])


def _parse_vtt(path: str) -> str | None:
    """
    Parse a WebVTT subtitle file into a clean plain-text string.
    Strips timestamps, cue settings, and duplicate lines.
    """
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return None

    lines, seen_text = [], set()
    for line in raw.splitlines():
        line = line.strip()
        # Skip header, blank lines, timestamps, and cue settings
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if "-->" in line:
            continue
        # Strip inline VTT tags like <00:00:01.000><c>text</c>
        import re
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line:
            continue
        # Deduplicate consecutive repeated lines (common in auto-captions)
        if line not in seen_text:
            seen_text.add(line)
            lines.append(line)

    return " ".join(lines) if lines else None


def fetch_transcripts_bulk(
    videos: list[dict],
    languages: list[str] | None = None,
) -> list[dict]:
    """Enrich a list of video dicts with a 'transcript' key."""
    for video in videos:
        video["transcript"] = fetch_transcript(video["video_id"], languages)
    return videos
