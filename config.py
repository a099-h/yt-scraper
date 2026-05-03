"""
config.py — Central configuration & env loading
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API ────────────────────────────────────────────────────────────────────────
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")

if not YOUTUBE_API_KEY:
    raise EnvironmentError(
        "YOUTUBE_API_KEY is not set.\n"
        "Copy .env.example → .env and fill in your key.\n"
        "Get one at https://console.developers.google.com/ (YouTube Data API v3)."
    )

# ── Scraping defaults ──────────────────────────────────────────────────────────
MAX_RESULTS_PER_CHANNEL: int = int(os.getenv("MAX_RESULTS", "50"))

# ── Ranking weights (must sum to 1.0) ─────────────────────────────────────────
RANK_WEIGHTS: dict = {
    "views":        0.40,
    "likes":        0.25,
    "comments":     0.20,
    "engagement":   0.10,   # (likes+comments) / views
    "duration_pts": 0.05,   # bonus points for longer videos vs shorts
}

# ── Output ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
