"""Field Risk Index: five indicators per field, combined with adjustable weights."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .panel import logit

COMPONENTS = {
    "level": "Not-working rate, 2023-2025 average",
    "trend": "Trend in gap to the national rate, 2020-2025",
    "low_skill": "Employed graduates in jobs below skilled level, 2024",
    "low_pay": "Employed degree holders earning RM2,000 or less, 2024",
    "routine": "Employed graduates in clerical or machine-operator jobs, 2024",
}
EQUAL_WEIGHTS = {k: 1 / len(COMPONENTS) for k in COMPONENTS}

# MASCO major groups 1-3 are the skilled occupations (DOSM's convention).
SKILLED = ["managers", "professionals", "technicians"]
BELOW_SKILLED = ["clerical", "service_sales", "skilled_agriculture", "craft", "operators", "elementary"]
ROUTINE = ["clerical", "operators"]
LOW_PAY_BANDS = ["le_1000", "1001_1500", "1501_2000"]


def _slope(years: pd.Series, values: pd.Series) -> float:
    return float(np.polyfit(years.to_numpy(float), values.to_numpy(float), 1)[0])


def components(ge: pd.DataFrame, jobs: pd.DataFrame, pay: pd.DataFrame) -> pd.DataFrame:
    """Raw indicator values per field. Higher always means more risk."""
    fields = ge[ge.field != "total"]
    rows = {}
    for field, g in fields.groupby("field"):
        g = g.set_index("year")
        rows[field] = {
            "level": g.loc[2023:2025, "nw_rate"].mean(),
            "trend": _slope(g.index.to_series(), g["gap"]),
            "low_skill": jobs.loc[field, BELOW_SKILLED].sum() / 100,
            "low_pay": pay.loc[field, LOW_PAY_BANDS].sum() / 100,
            "routine": jobs.loc[field, ROUTINE].sum() / 100,
        }
    return pd.DataFrame.from_dict(rows, orient="index")[list(COMPONENTS)]


def scores(raw: pd.DataFrame) -> pd.DataFrame:
    """Rescale each indicator to 0-1 across fields (0 = safest, 1 = riskiest)."""
    return (raw - raw.min()) / (raw.max() - raw.min())


def composite(score: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.Series:
    w = pd.Series(weights or EQUAL_WEIGHTS, dtype=float).reindex(score.columns).fillna(0.0)
    if w.sum() <= 0:
        raise ValueError("at least one weight must be positive")
    return (score * (w / w.sum())).sum(axis=1).rename("risk_index")


def pca_weights(raw: pd.DataFrame) -> tuple[pd.Series, float]:
    """First principal component of the standardised indicators.

    Returns the loadings (signed so that 'level' loads positively) and the
    share of variance the component explains.
    """
    z = (raw - raw.mean()) / raw.std(ddof=1)
    _, s, vt = np.linalg.svd(z.to_numpy(), full_matrices=False)
    loadings = pd.Series(vt[0], index=raw.columns)
    if loadings["level"] < 0:
        loadings = -loadings
    return loadings, float(s[0] ** 2 / (s**2).sum())


def rank_uncertainty(score: pd.DataFrame, draws: int = 10_000, seed: int = 0) -> pd.DataFrame:
    """How much each field's rank moves when the weights are drawn at random.

    Weights come from a flat Dirichlet, i.e. every mix of weights is equally
    likely. Rank 1 is the riskiest field.
    """
    rng = np.random.default_rng(seed)
    w = rng.dirichlet(np.ones(score.shape[1]), size=draws)
    idx = w @ score.to_numpy().T  # draws x fields
    ranks = (-idx).argsort(axis=1).argsort(axis=1) + 1
    out = pd.DataFrame(
        {
            "rank_median": np.median(ranks, axis=0),
            "rank_p05": np.percentile(ranks, 5, axis=0),
            "rank_p95": np.percentile(ranks, 95, axis=0),
            "prob_top3": (ranks <= 3).mean(axis=0),
        },
        index=score.index,
    )
    return out


def downturn_shock(old8: pd.DataFrame, to_parent: dict[str, str], fields: list[str]) -> pd.Series:
    """Logit rise in each field's not-working rate between 2019 and 2020.

    Measured on the earlier eight-field tables; a field that was split in 2022
    takes the value of the field it was split from.
    """
    w = old8[old8.field != "total"].pivot(index="year", columns="field", values="nw_rate")
    shock = logit(w.loc[2020]) - logit(w.loc[2019])
    return pd.Series({f: float(shock[to_parent.get(f, f)]) for f in fields})
