# 🎬 yt-scrapling

> Scrape YouTube channels · Fetch transcripts · Rank videos & shorts by weighted engagement metrics.

---

## Features

- **Channel scraping** — pull up to N videos/shorts from any public channel via YouTube Data API v3
- **Transcript fetching** — download auto-generated or manual captions (no extra quota cost)
- **Weighted ranking** — composite score from views, likes, comments, engagement rate & content type
- **Separate rankings** — side-by-side leaderboards for full videos vs Shorts
- **Export** — results saved as CSV and/or JSON in `output/`
- **Rich terminal UI** — colour tables, progress bars, banners

---

## Project Structure

```
yt-scrapling/
├── main.py                # CLI entry point
├── config.py              # API key, weights, defaults
├── requirements.txt
├── .env.example           # Copy to .env and fill in your key
├── .gitignore
│
├── scraper/
│   ├── __init__.py
│   └── youtube.py         # Channel → video list via Data API v3
│
├── transcript/
│   ├── __init__.py
│   └── fetcher.py         # Scrapling-based transcript scraper (no API key)
│
├── ranker/
│   ├── __init__.py
│   └── scorer.py          # Weighted composite scorer
│
├── output/
│   ├── __init__.py
│   └── exporter.py        # CSV / JSON export
│
├── utils/
│   ├── __init__.py
│   └── helpers.py         # Shared helpers (duration, formatting…)
│
└── tests/
    ├── test_helpers.py
    └── test_scorer.py
```

---

## Quick Start

### 1 — Get a YouTube API key

1. Go to [Google Cloud Console](https://console.developers.google.com/)
2. Create a project → **Enable** `YouTube Data API v3`
3. **Credentials** → Create API Key → copy it

### 2 — Clone & install

```bash
# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3 — Configure environment

```bash
cp .env.example .env
# Edit .env and paste your API key
```

`.env`:
```
YOUTUBE_API_KEY=AIzaSy...your_key_here
```

---

## Running

### Basic — scrape a channel and rank results

```bash
python main.py --channels UCxxxxxxxxxxxxxx
```

### Multiple channels

```bash
python main.py --channels UCxxxxxx UCyyyyyy UCzzzzzz
```

### With transcripts + custom limits

```bash
python main.py \
  --channels UCxxxxxxxxxxxxxx \
  --max 100 \
  --transcripts \
  --lang en es \
  --top 30 \
  --export csv json
```

### All flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--channels` | `-c` | *required* | Channel IDs (space-separated) |
| `--max` | `-m` | 50 | Max videos per channel |
| `--transcripts` | `-t` | off | Fetch transcripts via Scrapling (no API key) |
| `--stealth` | | off | Headless browser for transcripts (slower, bypasses blocks) |
| `--lang` | | `en` | Language preference for transcripts |
| `--export` | `-e` | `both` | `csv`, `json`, or `both` |
| `--top` | `-n` | 20 | Rows shown in terminal |

---

## How Ranking Works

Each video gets a **composite score** (0–1) from normalised signals:

| Signal | Default weight | Notes |
|--------|---------------|-------|
| Views | 40 % | Raw view count, min-max normalised |
| Likes | 25 % | Raw like count |
| Comments | 20 % | Raw comment count |
| Engagement rate | 10 % | `(likes+comments)/views` |
| Duration bonus | 5 % | 1 for full videos, 0 for Shorts |

Weights live in `config.py → RANK_WEIGHTS` — change them freely.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Output Files

Results land in `output/` (gitignored by default):

```
output/
├── yt_scrapling_20240901_142301.csv
└── yt_scrapling_20240901_142301.json
```

Each row contains: `rank`, `type_rank`, `content_type`, `title`, `views`, `likes`, `comments`, `engagement_rate`, `score`, `transcript`, `video_url`, …

---

## Finding Channel IDs

YouTube channel IDs start with `UC`. You can find them:
- In the channel URL: `youtube.com/channel/UCxxxxxx`
- Via [commentpicker.com/youtube-channel-id.php](https://commentpicker.com/youtube-channel-id.php)

---

## Quota Usage

The YouTube Data API v3 has a daily free quota of **10,000 units**.

| Operation | Units per call |
|-----------|---------------|
| `channels.list` | 1 |
| `playlistItems.list` | 1 |
| `videos.list` (50 ids) | 1 |

Scraping 100 videos ≈ **4 units**. Transcripts use **zero quota** (separate library).

---

## License

MIT
