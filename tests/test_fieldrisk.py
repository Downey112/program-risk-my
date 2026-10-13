import numpy as np
import pandas as pd
import pytest

from fieldrisk import forecast as fc
from fieldrisk import index as ix
from fieldrisk import panel as pn


def test_logit_round_trip():
    p = np.array([0.05, 0.5, 0.93])
    assert np.allclose(pn.inv_logit(pn.logit(p)), p)


def test_ge_panel_is_complete():
    ge = pn.load_ge()
    assert sorted(ge.year.unique()) == list(range(2020, 2026))
    assert ge.groupby("field").size().eq(6).all()
    assert ge.field.nunique() == 11  # ten fields plus the total
    assert ge.nw_rate.between(0.03, 0.25).all()


def test_ge_matches_published_figures():
    ge = pn.load_ge().set_index(["field", "year"])["nw_rate"]
    assert ge["total", 2023] == pytest.approx(0.091)  # GE 90.9%
    assert ge["engineering", 2024] == pytest.approx(0.051)  # GE 94.9%
    assert ge["education", 2025] == pytest.approx(0.116)  # GE 88.4%


def test_old_definition_runs_higher_than_new():
    old = pn.load_old8().query("field == 'total'").set_index("year")["nw_rate"]
    new = pn.load_ge().query("field == 'total'").set_index("year")["nw_rate"]
    gap = (old - new).dropna() * 100
    assert list(gap.index) == [2020, 2021, 2022, 2023]
    assert gap.between(3, 5).all()


def test_job_and_pay_tables_sum_to_100():
    jobs, pay = pn.load_jobs(), pn.load_pay()
    assert np.allclose(jobs.drop(columns="employed").sum(axis=1), 100, atol=0.3)
    assert np.allclose(pay.drop(columns="employed").sum(axis=1), 100, atol=0.3)


def test_scores_and_composite():
    raw = pd.DataFrame({"level": [1.0, 2.0, 3.0], "trend": [0.3, 0.1, 0.2]}, index=list("abc"))
    score = ix.scores(raw)
    assert score.min().eq(0).all() and score.max().eq(1).all()
    only_level = ix.composite(score, {"level": 2, "trend": 0})
    assert only_level.tolist() == [0.0, 0.5, 1.0]
    with pytest.raises(ValueError):
        ix.composite(score, {"level": 0, "trend": 0})


def test_rank_uncertainty_bounds():
    score = ix.scores(ix.components(pn.load_ge(), pn.load_jobs(), pn.load_pay()))
    ranks = ix.rank_uncertainty(score, draws=500)
    assert (ranks.rank_p05 <= ranks.rank_median).all() and (ranks.rank_median <= ranks.rank_p95).all()
    assert ranks.prob_top3.sum() == pytest.approx(3.0)


def test_forecast_methods_on_known_series():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert fc.naive(y, 2).tolist() == [4.0, 4.0]
    assert fc.drift(y, 2).tolist() == [5.0, 6.0]
    assert fc.mean3(y, 1).tolist() == [3.0]
    assert fc.pooled_drift(y, 2, pooled_step=-0.5).tolist() == [3.5, 3.0]


def test_backtest_and_forecast_band_contains_forecast():
    rates = pn.wide(pn.load_ge())
    bt = fc.backtest(rates)
    # six years, three training years minimum: origins 2022, 2023 and 2024
    assert sorted(bt.origin.unique()) == [2022, 2023, 2024]
    assert (bt.target - bt.origin == bt.h).all()
    out = fc.forecast(rates, bt, "naive")
    assert ((out.lower < out.forecast) & (out.forecast < out.upper)).all()
    last = rates.iloc[-1]
    assert np.allclose(out[out.h == 1].set_index("field")["forecast"], last[out[out.h == 1].field].to_numpy())


def test_downturn_shock_maps_split_fields_to_parent():
    old8 = pn.load_old8()
    shock = ix.downturn_shock(old8, pn.TO_NEC8, ["ict", "natural_sciences", "education"])
    assert shock["ict"] == shock["natural_sciences"]
    assert shock["education"] < 0 < shock["ict"]
