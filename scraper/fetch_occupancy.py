#!/usr/bin/env python3
"""Fetch current studio occupancy from AI Fitness Wuppertal and append to CSV."""

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

STUDIO_ID = "1281492160"
API_URL = f"https://www.ai-fitness.de/connect/v1/studio/{STUDIO_ID}/utilization"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_FILE = DATA_DIR / "occupancy.csv"


def fetch_utilization() -> dict:
    req = Request(API_URL)
    req.add_header("User-Agent", "AIBarmen-OccupancyTracker/1.0")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_current_occupancy(data: dict) -> tuple[int, str]:
    for item in data.get("items", []):
        if item.get("isCurrent"):
            return item["percentage"], item["level"]
    return -1, "UNKNOWN"


def main():
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    weekday = now.strftime("%A")

    try:
        data = fetch_utilization()
    except (URLError, HTTPError) as e:
        print(f"[{timestamp}] API error: {e}", file=sys.stderr)
        sys.exit(1)

    percentage, level = get_current_occupancy(data)

    current_slot = None
    for item in data.get("items", []):
        if item.get("isCurrent"):
            current_slot = f'{item["startTime"]}-{item["endTime"]}'
            break

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    write_header = not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["timestamp", "date", "time_utc", "weekday", "percentage", "level", "time_slot"])
        writer.writerow([timestamp, date_str, time_str, weekday, percentage, level, current_slot])

    print(f"[{timestamp}] Occupancy: {percentage}% ({level}) slot={current_slot}")


if __name__ == "__main__":
    main()
