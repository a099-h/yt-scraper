"""
main.py — CLI entry point for yt-scrapling.

Usage:
    python main.py --channels UC1xxxxx UC2xxxxx --max 100 --transcripts --export csv json
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

import config
from scraper import scrape_channel
from transcript import fetch_transcripts_bulk
from ranker import score_videos
from output import save_all, save_csv, save_json
from utils import format_number

console = Console()

BANNER = """[bold red]
 ██╗   ██╗████████╗    ███████╗ ██████╗██████╗  █████╗ ██████╗ ██╗     ██╗███╗   ██╗ ██████╗
 ╚██╗ ██╔╝╚══██╔══╝    ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║     ██║████╗  ██║██╔════╝
  ╚████╔╝    ██║       ███████╗██║     ██████╔╝███████║██████╔╝██║     ██║██╔██╗ ██║██║  ███╗
   ╚██╔╝     ██║       ╚════██║██║     ██╔══██╗██╔══██║██╔═══╝ ██║     ██║██║╚██╗██║██║   ██║
    ██║       ██║       ███████║╚██████╗██║  ██║██║  ██║██║     ███████╗██║██║ ╚████║╚██████╔╝
    ╚═╝       ╚═╝       ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝
[/bold red]"""


def build_table(df, title: str, limit: int = 20) -> Table:
    table = Table(
        title=title,
        box=box.ROUNDED,
        highlight=True,
        show_lines=False,
        header_style="bold magenta",
    )
    table.add_column("#",          style="dim",         width=4)
    table.add_column("Type",       style="cyan",        width=7)
    table.add_column("Title",      style="white",       max_width=42, no_wrap=True)
    table.add_column("Views",      style="green",       justify="right")
    table.add_column("Likes",      style="yellow",      justify="right")
    table.add_column("Comments",   style="blue",        justify="right")
    table.add_column("Eng %",      style="magenta",     justify="right")
    table.add_column("Score",      style="bold white",  justify="right")
    table.add_column("Transcript", style="dim",         width=10)

    for _, row in df.head(limit).iterrows():
        eng = f"{row.get('engagement_rate', 0)*100:.2f}%"
        has_tr = "✓" if row.get("transcript") else "—"
        table.add_row(
            str(int(row["rank"])),
            row.get("content_type", "Video"),
            row["title"],
            format_number(int(row["views"])),
            format_number(int(row["likes"])),
            format_number(int(row["comments"])),
            eng,
            f"{row['score']:.4f}",
            has_tr,
        )
    return table


def parse_args():
    parser = argparse.ArgumentParser(
        prog="yt-scrapling",
        description="Scrape YouTube channels, rank their videos & shorts, fetch transcripts.",
    )
    parser.add_argument(
        "--channels", "-c",
        nargs="+",
        required=True,
        metavar="CHANNEL_ID",
        help="One or more YouTube channel IDs (UCxxxxxxxxxxxxxxxx)",
    )
    parser.add_argument(
        "--max", "-m",
        type=int,
        default=config.MAX_RESULTS_PER_CHANNEL,
        metavar="N",
        help=f"Max videos to fetch per channel (default: {config.MAX_RESULTS_PER_CHANNEL})",
    )
    parser.add_argument(
        "--transcripts", "-t",
        action="store_true",
        help="Also fetch transcripts for each video (slower)",
    )
    parser.add_argument(
        "--lang",
        nargs="+",
        default=["en"],
        metavar="LANG",
        help="Transcript language preference order (default: en)",
    )
    parser.add_argument(
        "--export", "-e",
        nargs="+",
        choices=["csv", "json", "both"],
        default=["both"],
        help="Export format(s) for results",
    )
    parser.add_argument(
        "--top", "-n",
        type=int,
        default=20,
        help="Number of top results to display in terminal (default: 20)",
    )
    parser.add_argument(
        "--stealth",
        action="store_true",
        help="Use StealthyFetcher for transcripts (headless browser, slower but bypasses bot detection)",
    )
    return parser.parse_args()


def main():
    console.print(BANNER)
    args = parse_args()

    all_videos: list[dict] = []

    # ── 1. Scrape ─────────────────────────────────────────────────────────────
    console.rule("[bold red]Scraping channels")
    for ch_id in args.channels:
        console.print(f"\n[cyan]→[/cyan] Channel: [bold]{ch_id}[/bold]")
        try:
            videos = scrape_channel(ch_id, max_results=args.max)
            console.print(
                f"  [green]✓[/green] Fetched [bold]{len(videos)}[/bold] videos"
            )
            all_videos.extend(videos)
        except Exception as exc:
            console.print(f"  [red]✗ Error scraping {ch_id}: {exc}[/red]")

    if not all_videos:
        console.print("[bold red]No videos found. Exiting.[/bold red]")
        sys.exit(1)

    # ── 2. Transcripts (optional) ─────────────────────────────────────────────
    if args.transcripts:
        console.rule("[bold yellow]Fetching transcripts")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Downloading…", total=len(all_videos))
            for video in all_videos:
                from transcript import fetch_transcript
                video["transcript"] = fetch_transcript(video["video_id"], args.lang, use_stealth=args.stealth)
                progress.advance(task)

        n_with = sum(1 for v in all_videos if v.get("transcript"))
        console.print(
            f"[green]✓[/green] Transcripts found for "
            f"[bold]{n_with}[/bold] / {len(all_videos)} videos"
        )
    else:
        for v in all_videos:
            v.setdefault("transcript", None)

    # ── 3. Score & rank ───────────────────────────────────────────────────────
    console.rule("[bold blue]Ranking")
    df = score_videos(all_videos)
    console.print(f"[green]✓[/green] Scored {len(df)} videos")

    # ── 4. Display ────────────────────────────────────────────────────────────
    console.rule("[bold white]Top Results")
    console.print(build_table(df, f"Top {args.top} Videos & Shorts (all channels)", limit=args.top))

    # Split by type
    videos_df = df[df["content_type"] == "Video"].head(args.top)
    shorts_df  = df[df["content_type"] == "Short"].head(args.top)

    if not videos_df.empty:
        videos_df = videos_df.copy()
        videos_df["rank"] = range(1, len(videos_df) + 1)
        console.print(build_table(videos_df, "🎬 Top Videos", limit=args.top))
    if not shorts_df.empty:
        shorts_df = shorts_df.copy()
        shorts_df["rank"] = range(1, len(shorts_df) + 1)
        console.print(build_table(shorts_df, "⚡ Top Shorts", limit=args.top))

    # ── 5. Export ─────────────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"yt_scrapling_{timestamp}"
    exports = args.export

    saved: dict[str, str] = {}
    if "both" in exports or ("csv" in exports and "json" in exports):
        saved = save_all(df, stem)
    elif "csv" in exports:
        saved["csv"] = save_csv(df, f"{stem}.csv")
    elif "json" in exports:
        saved["json"] = save_json(df, f"{stem}.json")

    for fmt, path in saved.items():
        console.print(f"[green]✓[/green] Saved [bold]{fmt.upper()}[/bold] → {path}")

    console.print(
        Panel(
            f"[bold green]Done![/bold green] {len(df)} videos ranked across {len(args.channels)} channel(s).",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
