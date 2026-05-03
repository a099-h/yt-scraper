"""
tests/test_scorer.py
"""
import pytest
from ranker.scorer import score_videos


SAMPLE_VIDEOS = [
    {
        "video_id": "aaa",
        "title": "Big hit video",
        "channel_id": "UC123",
        "channel_title": "TestChan",
        "published_at": "2024-01-01T00:00:00Z",
        "duration_seconds": 600,
        "is_short": False,
        "views": 1_000_000,
        "likes": 50_000,
        "comments": 5_000,
        "thumbnail_url": "",
        "video_url": "",
    },
    {
        "video_id": "bbb",
        "title": "Tiny short",
        "channel_id": "UC123",
        "channel_title": "TestChan",
        "published_at": "2024-02-01T00:00:00Z",
        "duration_seconds": 45,
        "is_short": True,
        "views": 10_000,
        "likes": 500,
        "comments": 50,
        "thumbnail_url": "",
        "video_url": "",
    },
    {
        "video_id": "ccc",
        "title": "Medium video",
        "channel_id": "UC123",
        "channel_title": "TestChan",
        "published_at": "2024-03-01T00:00:00Z",
        "duration_seconds": 300,
        "is_short": False,
        "views": 200_000,
        "likes": 8_000,
        "comments": 800,
        "thumbnail_url": "",
        "video_url": "",
    },
]


def test_score_videos_returns_df():
    df = score_videos(SAMPLE_VIDEOS)
    assert len(df) == 3


def test_ranking_order():
    df = score_videos(SAMPLE_VIDEOS)
    # 'Big hit video' should be rank 1
    assert df.iloc[0]["video_id"] == "aaa"


def test_content_type_labels():
    df = score_videos(SAMPLE_VIDEOS)
    types = set(df["content_type"].unique())
    assert types == {"Video", "Short"}


def test_type_rank_starts_at_1():
    df = score_videos(SAMPLE_VIDEOS)
    for ctype in ["Video", "Short"]:
        min_rank = df[df["content_type"] == ctype]["type_rank"].min()
        assert min_rank == 1


def test_empty_input():
    df = score_videos([])
    assert df.empty
