from __future__ import annotations
import json, os
import pandas as pd
import config


def save_csv(df: pd.DataFrame, filename: str = "results.csv") -> str:
    path = os.path.join(config.OUTPUT_DIR, filename)
    df.to_csv(path, index=False)
    return path


def save_json(df: pd.DataFrame, filename: str = "results.json") -> str:
    path = os.path.join(config.OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2, default=str)
    return path


def save_all(df: pd.DataFrame, stem: str = "results") -> dict[str, str]:
    return {"csv": save_csv(df, f"{stem}.csv"), "json": save_json(df, f"{stem}.json")}
