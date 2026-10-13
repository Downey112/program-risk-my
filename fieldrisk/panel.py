"""Load the field-of-study tables.

Two series exist and they must not be joined end to end:

* `load_ge` - the Ministry's 2024 definition (not working as a share of
  graduates in the labour force), ten fields, 2020-2025. This is the series
  the index and the forecasts use.
* `load_old8` - the earlier tables, eight fields, 2018-2023. 'Not working'
  there also counts graduates who were not looking for work, so its rates run
  about four points higher. Used for the 2020 downturn and as extra backtest
  evidence.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
PANEL_CSV = PROCESSED / "tracer_field.csv"

# The 2022+ classification splits two of the 2018-2021 fields. Summing the
# split fields back together gives eight fields comparable across 2018-2023.
TO_NEC8 = {
    "social_journalism": "social_business_law",
    "business_law": "social_business_law",
    "natural_sciences": "science_math_computing",
    "ict": "science_math_computing",
}

LABELS = {
    "education": "Education",
    "arts_humanities": "Arts & Humanities",
    "social_business_law": "Social Sciences, Business & Law",
    "science_math_computing": "Science, Maths & Computing",
    "engineering": "Engineering, Manufacturing & Construction",
    "agriculture": "Agriculture & Veterinary",
    "health": "Health & Welfare",
    "services": "Services",
    "social_journalism": "Social Sciences, Journalism & Information",
    "business_law": "Business, Administration & Law",
    "natural_sciences": "Natural Sciences, Maths & Statistics",
    "ict": "Information & Communication Technologies",
    "arts_social": "Arts & Social Sciences",
    "science": "Science",
    "technical": "Technical Studies",
    "ict_old": "Information & Communication Technology",
    "total": "All fields",
}
SHORT = {
    "education": "Education",
    "arts_humanities": "Arts & Humanities",
    "engineering": "Engineering",
    "agriculture": "Agriculture",
    "health": "Health",
    "services": "Services",
    "social_journalism": "Social Sciences",
    "business_law": "Business & Law",
    "natural_sciences": "Natural Sciences",
    "ict": "ICT",
    "total": "All fields",
}

COUNTS = ["employed", "further_study", "upgrading_skills", "waiting_placement", "not_working", "respondents"]


def logit(p):
    return np.log(p / (1 - p))


def inv_logit(x):
    return 1 / (1 + np.exp(-x))


def _add_gap(df: pd.DataFrame) -> pd.DataFrame:
    national = df[df.field == "total"].set_index("year")["nw_rate"]
    df["national_nw_rate"] = df["year"].map(national)
    df["gap"] = logit(df["nw_rate"]) - logit(df["national_nw_rate"])
    df["label"] = df["field"].map(LABELS)
    return df.sort_values(["field", "year"]).reset_index(drop=True)


def load_ge() -> pd.DataFrame:
    """Ten fields plus 'total', 2020-2025, on the 2024 definition."""
    ge = pd.read_csv(PROCESSED / "ge_field.csv")
    ge["nw_rate"] = ge["not_working_rate"] / 100
    return _add_gap(ge[["year", "field", "nw_rate", "source"]].copy())


def load_old8() -> pd.DataFrame:
    """Eight harmonised fields plus 'total', 2018-2023, on the earlier tables.

    The rate is not working / (employed + not working), the closest match to
    the 2024 definition that the earlier tables allow.
    """
    raw = pd.read_csv(PANEL_CSV)
    raw = raw[raw.year.between(2018, 2023) & (raw.field != "generic")].copy()
    raw["field"] = raw["field"].replace(TO_NEC8)
    grouped = raw.groupby(["year", "field"], as_index=False)[COUNTS].sum(min_count=1)
    grouped["nw_rate"] = grouped["not_working"] / (grouped["employed"] + grouped["not_working"])
    return _add_gap(grouped)


def load_national_old() -> pd.DataFrame:
    """National rate on the earlier tables, 2014-2023 (both ways of counting)."""
    raw = pd.read_csv(PANEL_CSV)
    tot = raw[(raw.field == "total") & (raw.year <= 2023)].copy()
    tot["nw_share_of_respondents"] = tot["not_working"] / tot["respondents"]
    tot["nw_rate"] = tot["not_working"] / (tot["employed"] + tot["not_working"])
    return tot[["year", "respondents", "employed", "not_working", "nw_share_of_respondents", "nw_rate"]]


def load_jobs() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "jobs_field_2024.csv").set_index("field")


def load_pay() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "pay_degree_2024.csv").set_index("field")


def wide(panel: pd.DataFrame) -> pd.DataFrame:
    """Years by fields, not-working rate, without the 'total' column."""
    fields = panel[panel.field != "total"]
    return fields.pivot(index="year", columns="field", values="nw_rate")
