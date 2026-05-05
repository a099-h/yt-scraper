"""
main.py — yt-scrapling CLI. No API key. No .env file.

Usage:
    python main.py --channels @MrBeast
    python main.py --channels @MrBeast UCxxxxxx --max 100 --transcripts
    python main.py --channels @MrBeast --transcripts --stealth
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
from transcript import fetch_transcript
from ranker import score_videos
from output import save_all, save_csv, save_json
from utils import format_number

console = Console()

BANNER = """[bold red]
 ██╗   ██╗████████╗    ███████╗ ██████╗██████╗  █████╗ ██████╗ ██╗     ██╗███╗   ██╗  ██████╗
 ╚██╗ ██╔╝╚══██╔══╝    ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║     ██║████╗  ██║ ██╔════╝
  ╚████╔╝    ██║       ███████╗██║     ██████╔╝███████║██████╔╝██║     ██║██╔██╗ ██║ ██║  ███╗
   ╚██╔╝     ██║       ╚════██║██║     ██╔══██╗██╔══██║██╔═══╝ ██║     ██║██║╚██╗██║ ██║   ██║
    ██║       ██║       ███████║╚██████╗██║  ██║██║  ██║██║     ███████╗██║██║ ╚████║ ╚██████╔╝
    ╚═╝       ╚═╝       ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝
[/bold red]
[dim]              No API key · No .env · Powered by Scrapling + yt-dlp[/dim]
"""


def build_table(df, title: str, limit: int = 20) -> Table:
    t = Table(title=title, box=box.ROUNDED, highlight=True,
              show_lines=False, header_style="bold magenta")
    t.add_column("#",          style="dim",        width=4)
    t.add_column("Type",       style="cyan",       width=7)
    t.add_column("Title",      style="white",      max_width=44, no_wrap=True)
    t.add_column("Views",      style="green",      justify="right")
    t.add_column("Likes",      style="yellow",     justify="right")
    t.add_column("Comments",   style="blue",       justify="right")
    t.add_column("Eng %",      style="magenta",    justify="right")
    t.add_column("Score",      style="bold white", justify="right")
    t.add_column("Transcript", style="dim",        width=10)
    t.add_column("Description", style="dim",       max_width=40, no_wrap=True)

    for _, row in df.head(limit).iterrows():
        t.add_row(
            str(int(row["rank"])),
            row.get("content_type", "Video"),
            row["title"],
            format_number(int(row["views"])),
            format_number(int(row["likes"])),
            format_number(int(row["comments"])),
            f"{row.get('engagement_rate', 0)*100:.2f}%",
            f"{row['score']:.4f}",
            "✓" if row.get("transcript") else "—",
            (str(row.get("description", "") or "")[:80]) or "—",
        )
    return t


def parse_args():
    p = argparse.ArgumentParser(
        prog="yt-scrapling",
        description="Scrape & rank YouTube channels. No API key needed.",
    )
    p.add_argument("--channels", "-c", nargs="+", required=True, metavar="CHANNEL",
                   help="Channel ID (UCxxxx) or handle (@Name). Multiple allowed.")
    p.add_argument("--max", "-m", type=int, default=config.MAX_RESULTS_PER_CHANNEL,
                   metavar="N", help=f"Max videos per channel (default: {config.MAX_RESULTS_PER_CHANNEL})")
    p.add_argument("--transcripts", "-t", action="store_true",
                   help="Fetch transcripts via yt-dlp (no API key)")
    p.add_argument("--lang", nargs="+", default=["en"], metavar="LANG",
                   help="Transcript language codes in priority order (default: en)")
    p.add_argument("--stealth", action="store_true",
                   help="Use headless Chromium for channel scraping (slower, bypasses blocks)")
    p.add_argument("--export", "-e", nargs="+", choices=["csv", "json", "both"],
                   default=["both"], help="Export format (default: both)")
    p.add_argument("--top", "-n", type=int, default=20,
                   help="Rows to display in terminal (default: 20)")
    return p.parse_args()


def main():
    console.print(BANNER)
    args = parse_args()
    all_videos: list[dict] = []

    # ── 1. Scrape ──────────────────────────────────────────────────────────────
    console.rule("[bold red]Scraping channels")
    for ch in args.channels:
        console.print(f"\n[cyan]→[/cyan] [bold]{ch}[/bold]")
        try:
            vids = scrape_channel(ch, max_results=args.max, stealth=args.stealth)
            console.print(f"  [green]✓[/green] {len(vids)} videos collected")
            all_videos.extend(vids)
        except Exception as exc:
            console.print(f"  [red]✗ {exc}[/red]")

    if not all_videos:
        console.print("[bold red]No videos found. Try --stealth or check the channel name.[/bold red]")
        sys.exit(1)

    # ── 2. Transcripts ─────────────────────────────────────────────────────────
    if args.transcripts:
        console.rule("[bold yellow]Fetching transcripts via yt-dlp")
        with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                      BarColumn(), TaskProgressColumn(), console=console) as prog:
            task = prog.add_task("Downloading…", total=len(all_videos))
            for video in all_videos:
                video["transcript"] = fetch_transcript(video["video_id"], languages=args.lang)
                prog.advance(task)
        n = sum(1 for v in all_videos if v.get("transcript"))
        console.print(f"[green]✓[/green] Transcripts: [bold]{n}[/bold] / {len(all_videos)}")
    else:
        for v in all_videos:
            v.setdefault("transcript", None)

    # ── 3. Rank ────────────────────────────────────────────────────────────────
    console.rule("[bold blue]Ranking")
    df = score_videos(all_videos)
    console.print(f"[green]✓[/green] Scored {len(df)} videos")

    # ── 4. Display ─────────────────────────────────────────────────────────────
    console.rule("[bold white]Results")
    console.print(build_table(df, f"Top {args.top} — All content", limit=args.top))

    for ctype, emoji in [("Video", "🎬"), ("Short", "⚡")]:
        sub = df[df["content_type"] == ctype].head(args.top).copy()
        if not sub.empty:
            sub["rank"] = range(1, len(sub) + 1)
            console.print(build_table(sub, f"{emoji} Top {ctype}s", limit=args.top))

    # ── 5. Export ──────────────────────────────────────────────────────────────
    stem  = f"yt_scrapling_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    saved = {}
    if "both" in args.export or len(args.export) == 2:
        saved = save_all(df, stem)
    elif "csv" in args.export:
        saved["csv"] = save_csv(df, f"{stem}.csv")
    else:
        saved["json"] = save_json(df, f"{stem}.json")

    for fmt, path in saved.items():
        console.print(f"[green]✓[/green] {fmt.upper()} → {path}")

    console.print(Panel(
        f"[bold green]Done![/bold green] {len(df)} videos ranked · {len(args.channels)} channel(s)",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
