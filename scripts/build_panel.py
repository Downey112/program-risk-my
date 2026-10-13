"""Build the field-of-study panel from MOHE Graduate Tracer Study chapters.

Reads the 'by field of studies' table from each year's PDF and writes
data/processed/tracer_field.csv with one row per (year, field).

The PDFs differ in layout from year to year, so field names are not parsed
from the page. Instead each report year lists its fields in the order they are
printed (FIELD_ORDER) and the numeric rows are matched to that list. Every
table is then checked against its own printed total row.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "mohe"
OUT = ROOT / "data" / "processed"

OLD5 = ["arts_social", "science", "technical", "ict_old", "education"]
NEC8 = [
    "education",
    "arts_humanities",
    "social_business_law",
    "science_math_computing",
    "engineering",
    "agriculture",
    "health",
    "services",
]

# Fields in printed order, per report year.
FIELD_ORDER: dict[int, list[str]] = {
    2015: OLD5,
    2016: OLD5,
    2017: OLD5,
    2018: ["generic"] + NEC8,
    2019: NEC8,
    2020: NEC8,
    2021: NEC8,
    2022: [
        "education",
        "arts_humanities",
        "social_journalism",
        "natural_sciences",
        "business_law",
        "ict",
        "engineering",
        "agriculture",
        "health",
        "services",
    ],
    2023: [
        "generic",
        "education",
        "arts_humanities",
        "social_journalism",
        "business_law",
        "natural_sciences",
        "ict",
        "engineering",
        "agriculture",
        "health",
        "services",
    ],
    2024: [
        "engineering",
        "health",
        "education",
        "services",
        "business_law",
        "agriculture",
        "generic",
        "natural_sciences",
        "social_journalism",
        "arts_humanities",
        "ict",
    ],
    2025: [
        "education",
        "arts_humanities",
        "social_journalism",
        "business_law",
        "natural_sciences",
        "ict",
        "engineering",
        "agriculture",
        "health",
        "services",
        "generic",
    ],
}

# Which classification each report year uses.
SCHEME = {y: "old5" for y in (2015, 2016, 2017)}
SCHEME |= {y: "nec8" for y in (2018, 2019, 2020, 2021)}
SCHEME |= {y: "nec11" for y in (2022, 2023, 2024, 2025)}

STATUS5 = ["employed", "further_study", "upgrading_skills", "waiting_placement", "not_working"]
STATUS2 = ["employed", "not_working"]

NUM = r"\d[\d,]*(?:\.\d+)?"
TAIL = re.compile(rf"((?:{NUM}\s+)*{NUM})\s*$")


def numeric_tail(line: str) -> list[float]:
    """Return the run of numbers that ends the line, as floats."""
    m = TAIL.search(line.strip())
    if not m:
        return []
    return [float(tok.replace(",", "")) for tok in m.group(1).split()]


def field_page(pdf: pdfplumber.PDF) -> str:
    for page in pdf.pages:
        text = page.extract_text() or ""
        if re.search(r"Bidang\s+Pengajian|Field\s+of\s+Stud", text[:700], re.I):
            return text
    raise ValueError("no field-of-studies table found")


def parse_year(report_year: int) -> pd.DataFrame:
    pdf_path = next((RAW / str(report_year)).glob("*.pdf"))
    with pdfplumber.open(pdf_path) as pdf:
        text = field_page(pdf)

    fields = FIELD_ORDER[report_year]
    two_years = SCHEME[report_year] == "old5"  # each field printed for year and year-1
    statuses = STATUS5 if "Further Study" in text else STATUS2
    width = 2 * len(statuses) + 2  # count+% per status, then total count and 100

    rows = []
    for line in text.split("\n"):
        nums = numeric_tail(line)
        if two_years and len(nums) == width + 1 and nums[0] in (report_year, report_year - 1):
            rows.append((int(nums[0]), nums[1:]))
        elif not two_years and len(nums) == width:
            rows.append((report_year, nums))

    per_year = len(fields) + 1  # fields plus the printed total
    expected = per_year * (2 if two_years else 1)
    if len(rows) < expected:
        raise ValueError(f"{report_year}: found {len(rows)} numeric rows, expected {expected}")
    rows = rows[:expected]  # later rows on the page belong to another table

    records = []
    for year in sorted({y for y, _ in rows}):
        year_rows = [nums for y, nums in rows if y == year]
        labels = fields + ["total"]
        for label, nums in zip(labels, year_rows, strict=True):
            rec = {"year": year, "report_year": report_year, "scheme": SCHEME[report_year], "field": label}
            for i, status in enumerate(statuses):
                rec[status] = int(nums[2 * i])
            rec["respondents"] = int(nums[-2])
            records.append(rec)
    df = pd.DataFrame(records)

    # Each table must add up to its own printed total.
    count_cols = [c for c in STATUS5 + ["respondents"] if c in df.columns]
    for year, grp in df.groupby("year"):
        body = grp[grp.field != "total"][count_cols].sum()
        total = grp[grp.field == "total"][count_cols].iloc[0]
        diff = (body - total).abs()
        if diff.max() > 30:  # the reports carry small rounding/missing-info gaps
            raise ValueError(f"{report_year} table for {year} does not sum to its total:\n{diff}")
    return df


def main() -> None:
    panel = pd.concat([parse_year(y) for y in sorted(FIELD_ORDER)], ignore_index=True)

    # Years printed in two reports (2015, 2016): keep the later report's own-year figure.
    panel = panel.sort_values(["year", "field", "report_year"])
    overlap = panel[panel.duplicated(["year", "field"], keep=False)]
    panel = panel[panel.year == panel.report_year].copy()
    first = parse_year(2015)
    panel = pd.concat([first[first.year == 2014], panel], ignore_index=True)

    OUT.mkdir(parents=True, exist_ok=True)
    panel = panel.sort_values(["year", "field"]).reset_index(drop=True)
    panel.to_csv(OUT / "tracer_field.csv", index=False)
    overlap.to_csv(OUT / "tracer_field_overlap_check.csv", index=False)
    print(panel.groupby(["year", "scheme"]).size().to_string())
    print(f"\nwrote {len(panel)} rows to {OUT / 'tracer_field.csv'}")


if __name__ == "__main__":
    main()
