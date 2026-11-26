#!/usr/bin/env python3
"""Builds london/exhibitions.json from the museum sites plus london/manual.json.

    python3 scraper/scrape.py            # all sites
    python3 scraper/scrape.py Tate V&A   # just these (the rest are kept from the last run)

Run it about once a month, read the diff, then commit and push.
"""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import Fetcher, Listing, parse_range, warn  # noqa: E402
from sites.london import READERS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "london" / "exhibitions.json"
MANUAL = ROOT / "london" / "manual.json"
FORMAT_VERSION = 1


def main(only: list[str]) -> int:
    today = date.today()
    previous = _load(OUTPUT).get("exhibitions", [])
    fetch = Fetcher()
    exhibitions: list[dict] = []
    report: list[str] = []
    failed = False

    for name, reader in READERS.items():
        if only and name not in only:
            kept = [e for e in previous if e.get("source") == name]
            exhibitions += kept
            report.append(f"{name:22} kept {len(kept)} from last run")
            continue
        print(f"Reading {name}…", file=sys.stderr)
        try:
            listings = reader(fetch)
        except Exception as error:  # one broken site shouldn't stop the others
            traceback.print_exc()
            kept = [e for e in previous if e.get("source") == name]
            exhibitions += kept
            report.append(f"{name:22} FAILED ({error}); kept {len(kept)} from last run")
            failed = True
            continue
        entries = [e for e in (_entry(l, name, today) for l in listings) if e]
        if not entries:
            warn(f"{name}: nothing found — the site may have changed")
            failed = True
        exhibitions += entries
        report.append(f"{name:22} {len(entries)} exhibitions")

    manual = [e for e in (_manual_entry(m, today) for m in _load(MANUAL).get("exhibitions", [])) if e]
    exhibitions += manual
    report.append(f"{'manual.json':22} {len(manual)} exhibitions")

    exhibitions = _dedupe(exhibitions)
    exhibitions.sort(key=lambda e: (e["end"] or "9999", e["title"]))
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "version": FORMAT_VERSION,
        "city": "London",
        "updated": today.isoformat(),
        "note": "Titles, venues, dates and links only. Details belong to each museum: follow the link.",
        "exhibitions": exhibitions,
    }, ensure_ascii=False, indent=2) + "\n")

    print("\n".join(report))
    print(f"→ {len(exhibitions)} exhibitions written to {OUTPUT.relative_to(ROOT)}")
    return 1 if failed else 0


def _entry(listing: Listing, source: str, today: date) -> dict | None:
    start, end = listing.start, listing.end
    if not (start or end):
        start, end = parse_range(listing.dates, today)
    if not (start or end):
        warn(f"{source}: couldn't read dates {listing.dates!r} for {listing.title!r}")
        return None
    if end and end < today:
        return None  # already closed
    return {
        "id": hashlib.sha1(listing.url.encode()).hexdigest()[:12],
        "title": listing.title,
        "venue": listing.venue,
        "url": listing.url,
        "start": start.isoformat() if start else None,  # null: already open
        "end": end.isoformat() if end else None,  # null: not announced
        "dates": listing.dates,  # as the site shows it
        "source": source,
    }


def _manual_entry(item: dict, today: date) -> dict | None:
    end = item.get("end")
    if end and date.fromisoformat(end) < today:
        return None
    return {
        "id": hashlib.sha1(item["url"].encode()).hexdigest()[:12],
        "title": item["title"],
        "venue": item["venue"],
        "url": item["url"],
        "start": item.get("start"),
        "end": end,
        "dates": item.get("dates", ""),
        "source": "manual",
    }


def _dedupe(exhibitions: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for e in exhibitions:
        seen.setdefault(e["url"].rstrip("/").lower(), e)
    return list(seen.values())


def _load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
