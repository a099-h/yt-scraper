from __future__ import annotations
import pandas as pd
import config


def _minmax(series: pd.Series) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([0.0] * len(series), index=series.index)
    return (series - mn) / (mx - mn)


def score_videos(videos: list[dict]) -> pd.DataFrame:
    if not videos:
        return pd.DataFrame()

    df = pd.DataFrame(videos)
    for col in ("views", "likes", "comments", "duration_seconds"):
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)

    if "is_short" not in df.columns:
        df["is_short"] = False

    df["engagement_rate"] = df.apply(
        lambda r: (r["likes"] + r["comments"]) / r["views"] if r["views"] > 0 else 0.0,
        axis=1,
    )
    df["duration_pts"] = (~df["is_short"]).astype(float)

    w = config.RANK_WEIGHTS
    df["score"] = (
        w["views"]        * _minmax(df["views"])
      + w["likes"]        * _minmax(df["likes"])
      + w["comments"]     * _minmax(df["comments"])
      + w["engagement"]   * _minmax(df["engagement_rate"])
      + w["duration_pts"] * _minmax(df["duration_pts"])
    )

    df.sort_values("score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["rank"] = df.index + 1
    df["content_type"] = df["is_short"].map({True: "Short", False: "Video"})
    df["type_rank"] = (
        df.groupby("content_type")["score"]
        .rank(ascending=False, method="min")
        .astype(int)
    )
    df.drop(columns=["duration_pts"], inplace=True)
    return df
