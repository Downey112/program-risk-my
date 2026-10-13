"""Build the field tables that use the Ministry's 2024 definition.

From 2024 the Ministry reports 'Graduate Employment' (GE): employed graduates
as a share of graduates in the labour force. Its Graduate Tracer Study report
for 2024 restates 2020-2023 on that definition, by field of study. This script
reads three tables from that report:

    Table 8h  GE by field, 2020-2024
    Table 4k  occupation group of employed graduates by field, 2024
    Table 4o  monthly income of employed first-degree graduates by field, 2024

and adds 2025 from the statistics chapter already parsed by build_panel.py.

Writes data/processed/ge_field.csv, jobs_field_2024.csv and pay_degree_2024.csv.
The report is fetched to data/raw/mohe/skpg/ if it is not there yet (30 MB).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pypdfium2 as pdfium
import requests

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "raw" / "mohe" / "skpg" / "LaporanSKPG2024.pdf"
REPORT_URL = "https://great.mohe.gov.my/Admin/UploadPenerbitan/LaporanSKPG2024c.pdf"
OUT = ROOT / "data" / "processed"

# Field names as the report prints them (whitespace and '&'/'dan' vary).
FIELDS = {
    "engineering": "Kejuruteraan, pembuatan dan pembinaan",
    "ict": "Teknologi maklumat dan komunikasi",
    "health": "Kesihatan dan kebajikan",
    "natural_sciences": "Sains semulajadi, matematik dan statistik",
    "business_law": "Perniagaan, pentadbiran dan perundangan",
    "arts_humanities": "Sastera dan kemanusiaan",
    "social_journalism": "Sains sosial, kewartawanan dan maklumat",
    "agriculture": "Pertanian, perhutanan, perikanan dan veterinar",
    "services": "Perkhidmatan",
    "education": "Pendidikan",
    "total": "Keseluruhan",
}

OCCUPATIONS = [
    "managers",
    "professionals",
    "technicians",
    "clerical",
    "service_sales",
    "skilled_agriculture",
    "craft",
    "operators",
    "elementary",
    "armed_forces",
]
INCOME_BANDS = [
    "le_1000",
    "1001_1500",
    "1501_2000",
    "2001_2500",
    "2501_3000",
    "3001_4000",
    "4001_5000",
    "5001_10000",
    "gt_10000",
]

NUM = r"(?:\d[\d,]*(?:\.\d+)?|-)"


def fetch_report() -> None:
    if REPORT.exists() and REPORT.stat().st_size > 1_000_000:
        return
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(REPORT_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=300)
    r.raise_for_status()
    REPORT.write_bytes(r.content)


def find_page(pdf: pdfium.PdfDocument, marker: str, start: int = 30) -> str:
    """Text of the first page after the contents pages that carries `marker`."""
    for i in range(start, len(pdf)):
        textpage = pdf[i].get_textpage()
        text = re.sub(r"\s+", " ", textpage.get_text_range())
        textpage.close()
        if marker in text:
            return text
    raise ValueError(f"table not found: {marker}")


def to_float(tok: str) -> float:
    return float("nan") if tok == "-" else float(tok.replace(",", ""))


def rows(text: str, n_values: int, total: bool = True) -> dict[str, list[float]]:
    """For each field, the `n_values` numbers that follow its name."""
    out = {}
    for key, name in FIELDS.items():
        if key == "total" and not total:
            continue
        words = [re.escape(w) for w in name.replace(" dan ", " ").split()]
        pattern = r"\s+(?:dan\s+|&\s+)?".join(words)
        m = re.search(rf"(?<!\w){pattern}\s+((?:{NUM}\s+){{{n_values - 1}}}{NUM})(?!\S)", text)
        if not m:
            raise ValueError(f"row not found for {key}")
        out[key] = [to_float(t) for t in m.group(1).split()]
    return out


def ge_trend(pdf: pdfium.PdfDocument) -> pd.DataFrame:
    text = find_page(pdf, "Jadual 8h")
    text = text[text.index("Bidang pengajian Tahun") :]
    records = []
    for key, values in rows(text, 5, total=False).items():
        for year, ge in zip(range(2020, 2025), values, strict=True):
            records.append({"year": year, "field": key, "ge": ge, "source": "SKPG 2024 report, Table 8h"})
    # National figures are printed on the chart before the table (Chart 8.2a).
    for year, ge in zip(range(2020, 2025), [83.6, 85.2, 91.1, 90.9, 92.5], strict=True):
        records.append({"year": year, "field": "total", "ge": ge, "source": "SKPG 2024 report, Chart 8.2a"})
    return pd.DataFrame(records)


def ge_2025() -> pd.DataFrame:
    """2025 comes from the statistics chapter, which prints counts."""
    panel = pd.read_csv(OUT / "tracer_field.csv")
    cur = panel[(panel.year == 2025) & (panel.field != "generic")].copy()
    cur["ge"] = (cur.employed / (cur.employed + cur.not_working) * 100).round(1)
    cur["source"] = "Statistik Pendidikan Tinggi 2025, Table 7.3"
    return cur[["year", "field", "ge", "source"]]


def jobs(pdf: pdfium.PdfDocument) -> pd.DataFrame:
    text = find_page(pdf, "Jadual 4k")
    text = text[text.index("Angkatan tentera") :]
    df = pd.DataFrame.from_dict(rows(text, 11), orient="index", columns=["employed", *OCCUPATIONS])
    df[OCCUPATIONS] = df[OCCUPATIONS].fillna(0.0)
    if (df[OCCUPATIONS].sum(axis=1) - 100).abs().max() > 0.3:
        raise ValueError("Table 4k rows do not sum to 100")
    return df.rename_axis("field").reset_index()


def pay(pdf: pdfium.PdfDocument) -> pd.DataFrame:
    text = find_page(pdf, "Jadual 4o")
    start = text.index("Ijazah pertama Perniagaan")
    text = text[start : text.index("Nota:", start)]  # first-degree block only
    df = pd.DataFrame.from_dict(rows(text, 10), orient="index", columns=["employed", *INCOME_BANDS])
    df[INCOME_BANDS] = df[INCOME_BANDS].fillna(0.0)
    if (df[INCOME_BANDS].sum(axis=1) - 100).abs().max() > 0.3:
        raise ValueError("Table 4o rows do not sum to 100")
    return df.rename_axis("field").reset_index()


def main() -> None:
    fetch_report()
    pdf = pdfium.PdfDocument(str(REPORT))
    ge = pd.concat([ge_trend(pdf), ge_2025()], ignore_index=True)
    ge["not_working_rate"] = (100 - ge["ge"]).round(1)
    ge = ge.sort_values(["field", "year"]).reset_index(drop=True)

    # The report's 2024 column must agree with the 2024 statistics chapter.
    panel = pd.read_csv(OUT / "tracer_field.csv")
    chapter = panel[panel.year == 2024].set_index("field")
    chapter_ge = chapter.employed / (chapter.employed + chapter.not_working) * 100
    report_ge = ge[ge.year == 2024].set_index("field")["ge"]
    gap = (report_ge - chapter_ge.reindex(report_ge.index)).abs().max()
    if gap > 0.06:
        raise ValueError(f"2024 figures differ between report and chapter by {gap:.2f} points")

    ge.to_csv(OUT / "ge_field.csv", index=False)
    jobs(pdf).to_csv(OUT / "jobs_field_2024.csv", index=False)
    pay(pdf).to_csv(OUT / "pay_degree_2024.csv", index=False)
    print(ge.pivot(index="field", columns="year", values="not_working_rate").to_string())
    print(f"\n2024 report vs chapter: largest difference {gap:.2f} points")


if __name__ == "__main__":
    main()
