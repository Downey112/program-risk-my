"""Run the analysis: risk index, weight sensitivity, backtest and forecasts.

Writes CSVs to results/. Run scripts/build_panel.py and scripts/build_ge.py first.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fieldrisk import forecast as fc  # noqa: E402
from fieldrisk import index as ix  # noqa: E402
from fieldrisk import panel as pn  # noqa: E402

RESULTS = ROOT / "results"
CURRENT = "2024 definition, 2020-2025"


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    ge, old8 = pn.load_ge(), pn.load_old8()
    jobs, pay = pn.load_jobs(), pn.load_pay()
    ge.to_csv(RESULTS / "field_panel.csv", index=False)
    old8.to_csv(RESULTS / "field_panel_old_definition.csv", index=False)

    # National series: earlier tables to 2023, the 2024 definition from 2020.
    national = pn.load_national_old().merge(
        ge[ge.field == "total"][["year", "nw_rate"]].rename(columns={"nw_rate": "nw_rate_2024_definition"}),
        on="year",
        how="outer",
    )
    national.to_csv(RESULTS / "national.csv", index=False)

    # Risk index
    comp = ix.components(ge, jobs, pay)
    score = ix.scores(comp)
    risk = ix.composite(score)
    loadings, explained = ix.pca_weights(comp)
    ranks = ix.rank_uncertainty(score)
    table = comp.add_prefix("raw_").join(score.add_prefix("score_")).join(risk).join(ranks)
    table["rank"] = table["risk_index"].rank(ascending=False, method="min").astype(int)
    table.insert(0, "label", table.index.map(pn.LABELS))
    table = table.sort_values("rank")
    table.index.name = "field"
    table.to_csv(RESULTS / "risk_index.csv")
    pd.DataFrame({"loading": loadings, "explained_variance": explained}).to_csv(RESULTS / "pca.csv")
    comp.corr(method="spearman").to_csv(RESULTS / "indicator_correlations.csv")

    # Backtest on both series; each is consistent within itself.
    rates = pn.wide(ge)
    bt = pd.concat(
        [
            fc.backtest(rates).assign(series=CURRENT),
            fc.backtest(pn.wide(old8)).assign(series="earlier tables, 2018-2023"),
        ],
        ignore_index=True,
    )
    bt.to_csv(RESULTS / "backtest.csv", index=False)
    acc = fc.accuracy(bt)
    acc.to_csv(RESULTS / "backtest_accuracy.csv", index=False)
    by_series = bt.groupby(["series", "method"])["abs_error_pp"].mean().unstack("series")
    by_series.to_csv(RESULTS / "backtest_by_series.csv")
    overall = bt.groupby("method")["abs_error_pp"].mean().sort_values()
    # The method is chosen on the series being forecast. The band still uses
    # that method's errors on both series, so it reflects the 2020 downturn and
    # the 2022 recovery rather than only the calm years since.
    best = by_series[CURRENT].idxmin()

    baseline = fc.forecast(rates, bt, best).assign(scenario="baseline")
    shock = ix.downturn_shock(old8, pn.TO_NEC8, list(rates.columns))
    stress = fc.forecast(rates, bt, best, shock=shock).assign(scenario="downturn")
    forecasts = pd.concat([baseline, stress], ignore_index=True)
    forecasts["method"] = best
    forecasts["label"] = forecasts["field"].map(pn.LABELS)
    forecasts.to_csv(RESULTS / "forecasts.csv", index=False)
    shock.rename("logit_shift").rename_axis("field").to_csv(RESULTS / "downturn_shock.csv")

    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    print("NATIONAL not-working rate")
    print((national.set_index("year")[["nw_share_of_respondents", "nw_rate", "nw_rate_2024_definition"]] * 100).round(1).to_string())
    print("\nFIELD not-working rate %, 2024 definition")
    print((rates * 100).round(1).to_string())
    print("\nRISK INDEX (equal weights)")
    print(table[["label", "risk_index", "rank", "rank_p05", "rank_p95", "prob_top3"]].to_string())
    print("\nRaw components")
    print(comp.to_string())
    print("\nSpearman correlations between indicators")
    print(comp.corr(method="spearman").to_string())
    print(f"\nPCA first component explains {explained:.0%}; loadings:")
    print(loadings.to_string())
    print("\nBACKTEST mean absolute error (percentage points)")
    print(by_series.assign(both=overall).sort_values("both").to_string())
    print(acc.pivot(index="method", columns="h", values="mae_pp").to_string())
    print(acc[acc.method == best][["h", "n", "origins"]].to_string(index=False))
    print(f"\nFORECASTS with '{best}', 80% band")
    show = forecasts.assign(
        v=lambda d: (d.forecast * 100).round(1).astype(str)
        + " ["
        + (d.lower * 100).round(1).astype(str)
        + ", "
        + (d.upper * 100).round(1).astype(str)
        + "]"
    )
    print(show.pivot(index=["scenario", "field"], columns="year", values="v").to_string())


if __name__ == "__main__":
    main()
