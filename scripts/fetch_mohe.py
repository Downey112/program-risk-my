"""Download chapters of MOHE's annual 'Statistik Pendidikan Tinggi' report.

Each year has its own page on mohe.gov.my listing one PDF per chapter. This
script reads those pages and saves the chapters we use to data/raw/mohe/<year>/.

Usage:
    python scripts/fetch_mohe.py              # tracer-study chapter, all years
    python scripts/fetch_mohe.py --all        # every chapter
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import requests

BASE = "https://www.mohe.gov.my"
INDEX = f"{BASE}/muat-turun/statistik"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "mohe"
HEADERS = {"User-Agent": "Mozilla/5.0 (research; program-risk-my)"}

# Report year -> page slug. The slugs are irregular, so they are listed here
# rather than derived.
YEAR_PAGES = {
    2015: "stat-2015",
    2016: "stat-2016",
    2017: "stat-2017",
    2018: "stat-2018",
    2019: "stat-2019",
    2020: "2020",
    2021: "2021-1",
    2022: "2022-3",
    2023: "2023-3",
    2024: "2024-4",
    2025: "2025-1-1",
}

TRACER = re.compile(r"tracer|pengesanan|skpg|bab-7/file", re.I)


def get(url: str, tries: int = 4) -> requests.Response:
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=120)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise AssertionError("unreachable")


def chapter_links(slug: str) -> list[str]:
    html = get(f"{INDEX}/{slug}").text
    pattern = rf'href="(/muat-turun/statistik/{re.escape(slug)}/[^"]+/file)"'
    return sorted(set(re.findall(pattern, html)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="download every chapter")
    ap.add_argument("--years", nargs="*", type=int, default=sorted(YEAR_PAGES))
    args = ap.parse_args()

    for year in args.years:
        links = chapter_links(YEAR_PAGES[year])
        if not args.all:
            links = [u for u in links if TRACER.search(u)]
        if not links:
            print(f"{year}: no matching chapter found")
            continue
        out_dir = RAW / str(year)
        out_dir.mkdir(parents=True, exist_ok=True)
        for link in links:
            name = link.split("/")[-2] + ".pdf"
            dest = out_dir / name
            if dest.exists() and dest.stat().st_size > 10_000:
                print(f"{year}: have {name}")
                continue
            body = get(BASE + link).content
            if not body.startswith(b"%PDF"):
                print(f"{year}: {name} is not a PDF, skipped")
                continue
            dest.write_bytes(body)
            print(f"{year}: saved {name} ({len(body) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
