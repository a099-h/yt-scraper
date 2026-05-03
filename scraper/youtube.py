"""
scraper/youtube.py — Fetch videos & shorts from a YouTube channel via the Data API v3.
"""
from __future__ import annotations
from typing import Generator
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tqdm import tqdm

import config
from utils import parse_duration_seconds, is_short, safe_int


# ── Build the API client once ──────────────────────────────────────────────────
_YT = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)


def _get_uploads_playlist_id(channel_id: str) -> str:
    """Resolve a channel ID → its 'uploads' playlist ID."""
    resp = _YT.channels().list(
        part="contentDetails",
        id=channel_id,
    ).execute()

    items = resp.get("items", [])
    if not items:
        raise ValueError(f"Channel not found or no access: {channel_id}")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def _iter_playlist_video_ids(playlist_id: str, max_results: int) -> Generator[str, None, None]:
    """Yield video IDs from a playlist, paginating automatically."""
    fetched = 0
    page_token = None

    while fetched < max_results:
        batch = min(50, max_results - fetched)
        resp = _YT.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=batch,
            pageToken=page_token,
        ).execute()

        for item in resp.get("items", []):
            yield item["contentDetails"]["videoId"]
            fetched += 1

        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def _fetch_video_details(video_ids: list[str]) -> list[dict]:
    """Batch-fetch statistics + content details for up to 50 video IDs at once."""
    results = []
    # API allows max 50 per request
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        resp = _YT.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(chunk),
        ).execute()
        results.extend(resp.get("items", []))
    return results


def scrape_channel(channel_id: str, max_results: int | None = None) -> list[dict]:
    """
    Scrape a channel and return a list of video dicts with all raw + computed fields.

    Each dict keys:
        video_id, title, published_at, channel_id, channel_title,
        duration_seconds, is_short, views, likes, comments,
        thumbnail_url, video_url
    """
    if max_results is None:
        max_results = config.MAX_RESULTS_PER_CHANNEL

    playlist_id = _get_uploads_playlist_id(channel_id)
    video_ids = list(
        tqdm(
            _iter_playlist_video_ids(playlist_id, max_results),
            total=max_results,
            desc=f"  Collecting IDs [{channel_id[:12]}…]",
            unit="vid",
            leave=False,
        )
    )

    raw_items = _fetch_video_details(video_ids)

    videos = []
    for item in raw_items:
        vid_id      = item["id"]
        snippet     = item.get("snippet", {})
        stats       = item.get("statistics", {})
        content     = item.get("contentDetails", {})

        duration_s  = parse_duration_seconds(content.get("duration", "PT0S"))
        title       = snippet.get("title", "")
        description = snippet.get("description", "")

        views    = safe_int(stats.get("viewCount", 0))
        likes    = safe_int(stats.get("likeCount", 0))
        comments = safe_int(stats.get("commentCount", 0))

        videos.append(
            {
                "video_id":       vid_id,
                "title":          title,
                "published_at":   snippet.get("publishedAt", ""),
                "channel_id":     snippet.get("channelId", channel_id),
                "channel_title":  snippet.get("channelTitle", ""),
                "duration_seconds": duration_s,
                "is_short":       is_short(duration_s, title, description),
                "views":          views,
                "likes":          likes,
                "comments":       comments,
                "thumbnail_url":  (
                    snippet.get("thumbnails", {})
                    .get("high", {})
                    .get("url", "")
                ),
                "video_url":      f"https://www.youtube.com/watch?v={vid_id}",
            }
        )

    return videos
