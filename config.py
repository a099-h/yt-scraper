"""
config.py — Simple config. No API key. No .env file needed.
Tweak values here directly, or they work fine as defaults.
"""

# Max videos to scrape per channel (split between /videos and /shorts tabs)
MAX_RESULTS_PER_CHANNEL: int = 50

# Use headless Chromium for channel scraping (slower but bypasses bot detection)
# Set to True if you get blocked with the default plain HTTP mode
USE_STEALTH: bool = False

# Ranking weights — must sum to 1.0
RANK_WEIGHTS: dict = {
    "views":        0.40,
    "likes":        0.25,
    "comments":     0.20,
    "engagement":   0.10,
    "duration_pts": 0.05,
}

import os
OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
