"""
ranker/scorer.py — Score and rank videos/shorts by weighted metrics.

Scoring formula (configurable in config.py → RANK_WEIGHTS):
  - views        : raw view count (normalised 0-1 within dataset)
  - likes        : raw like count (normalised)
  - comments     : raw comment count (normalised)
  - engagement   : (likes + comments) / views  (normalised)
  - duration_pts : bonus for full videos over shorts (binary 0 or 1)
"""
from __future__ import annotations
import pandas as pd
import config


def _minmax(series: pd.Series) -> pd.Series:
    """Min-max normalise a Series to [0, 1]. Returns 0 for constant series."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([0.0] * len(series), index=series.index)
    return (series - mn) / (mx - mn)


def score_videos(videos: list[dict]) -> pd.DataFrame:
    """
    Given a list of video dicts (output of scraper + transcript fetcher),
    return a scored & sorted DataFrame with a 'score' and 'rank' column.

    Separate rankings are produced for videos vs shorts via the 'content_type' col.
    """
    if not videos:
        return pd.DataFrame()

    df = pd.DataFrame(videos)

    # Ensure numeric cols exist
    for col in ("views", "likes", "comments", "duration_seconds"):
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    if "is_short" not in df.columns:
        df["is_short"] = False

    # ── Engagement rate ──────────────────────────────────────────────────────
    df["engagement_rate"] = df.apply(
        lambda r: (r["likes"] + r["comments"]) / r["views"] if r["views"] > 0 else 0.0,
        axis=1,
    )

    # ── Duration bonus: full video = 1, short = 0 ────────────────────────────
    df["duration_pts"] = (~df["is_short"]).astype(float)

    # ── Normalise raw signals ─────────────────────────────────────────────────
    df["n_views"]       = _minmax(df["views"])
    df["n_likes"]       = _minmax(df["likes"])
    df["n_comments"]    = _minmax(df["comments"])
    df["n_engagement"]  = _minmax(df["engagement_rate"])
    df["n_duration"]    = _minmax(df["duration_pts"])

    # ── Weighted composite score ──────────────────────────────────────────────
    w = config.RANK_WEIGHTS
    df["score"] = (
        w["views"]        * df["n_views"]
      + w["likes"]        * df["n_likes"]
      + w["comments"]     * df["n_comments"]
      + w["engagement"]   * df["n_engagement"]
      + w["duration_pts"] * df["n_duration"]
    )

    # ── Global rank ───────────────────────────────────────────────────────────
    df.sort_values("score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["rank"] = df.index + 1

    # ── Content type label ────────────────────────────────────────────────────
    df["content_type"] = df["is_short"].map({True: "Short", False: "Video"})

    # ── Per-type rank (rank within videos, rank within shorts) ───────────────
    df["type_rank"] = (
        df.groupby("content_type")["score"]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    # ── Clean up intermediate cols ────────────────────────────────────────────
    df.drop(
        columns=["n_views", "n_likes", "n_comments", "n_engagement", "n_duration", "duration_pts"],
        inplace=True,
    )

    return df
