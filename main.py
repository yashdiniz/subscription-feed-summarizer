"""Fetch RSS/Atom feeds, filter by time window, output recent items as JSON."""

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys

import feedparser
import pandas as pd
import toons

# Ensure we can import from the root directory
sys.path.append(os.path.abspath(os.getcwd()))
from llm import generate_structured_articles

# Setup logging
logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


LAST_RUN_FILE = "last_run.txt"
DEFAULT_CSV = "feeds.csv"
BUFFER_SECONDS = 600  # overlap window like n8n "Keep recent"
DEFAULT_LIMIT = 50


def get_last_run() -> datetime:
    try:
        return datetime.fromisoformat(
            Path(LAST_RUN_FILE).read_text().strip()
        ).astimezone(timezone.utc)
    except (FileNotFoundError, ValueError):
        return datetime.fromtimestamp(0, tz=timezone.utc)


def save_last_run() -> None:
    Path(LAST_RUN_FILE).write_text(datetime.now(timezone.utc).isoformat())


def parse_entry(entry, feed_title: str) -> dict | None:
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if not published:
        return None
    published_dt = datetime(*published[:6], tzinfo=timezone.utc)
    return {
        "title": entry.get("title", ""),
        "link": entry.get("link", ""),
        "author": entry.get("author") or entry.get("creator", "") or feed_title,
        "summary": (entry.get("summary") or entry.get("description", "")).strip(),
        "published": published_dt.isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent RSS/Atom feed items.")
    parser.add_argument(
        "--after",
        help="Only items after this datetime (ISO 8601). Default: last run time.",
    )
    parser.add_argument(
        "--file",
        default=DEFAULT_CSV,
        help=f"CSV with name,url,active columns. Default: {DEFAULT_CSV}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Max items to output. Default: {DEFAULT_LIMIT}.",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.file)
    active = df[df.get("active")]
    logger.info(f"Loaded {len(active)} active feeds from {args.file}")

    if args.after:
        cutoff = datetime.fromisoformat(args.after).astimezone(timezone.utc)
        logger.info(f"Using manual cutoff: {cutoff}")
    else:
        last_run = get_last_run()
        # ponytail: global cutoff, per-feed tracking if per-feed timestamps matter
        cutoff = datetime.fromtimestamp(
            last_run.timestamp() - BUFFER_SECONDS, tz=timezone.utc
        )
        logger.info(f"Using cutoff from last run: {cutoff}")

    all_items: list[dict] = []
    for url in active["url"]:
        logger.info(f"Fetching {url}")
        feed = feedparser.parse(url)
        for entry in feed.entries:
            item = parse_entry(entry, feed.feed.get("title", ""))
            if (
                item
                and datetime.fromisoformat(item["published"]).astimezone(timezone.utc)
                >= cutoff
            ):
                all_items.append(item)

    logger.info(f"Found {len(all_items)} total items")

    all_items.sort(key=lambda x: x["published"], reverse=True)
    result = all_items[: args.limit]
    logger.info(json.dumps(result, indent=2))

    # ponytail: generate_structured_articles call
    logger.info("Generating structured articles via LLM")
    res = generate_structured_articles(toons.dumps(result)).model_dump()

    if not args.after:
        save_last_run()
        logger.info(f"Updated {LAST_RUN_FILE}")

    print(toons.dumps(res))


if __name__ == "__main__":
    main()
