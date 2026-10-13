"""Short-horizon forecasts of the not-working rate, with a rolling-origin backtest.

Each field has one observation a year, so only simple methods are used. All
of them work on the logit of the rate, which keeps forecasts between 0 and 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .panel import inv_logit, logit


def naive(y: np.ndarray, h: int, **_) -> np.ndarray:
    return np.repeat(y[-1], h)


def drift(y: np.ndarray, h: int, **_) -> np.ndarray:
    step = (y[-1] - y[0]) / (len(y) - 1)
    return y[-1] + step * np.arange(1, h + 1)


def mean3(y: np.ndarray, h: int, **_) -> np.ndarray:
    return np.repeat(y[-3:].mean(), h)


def ses(y: np.ndarray, h: int, **_) -> np.ndarray:
    """Simple exponential smoothing; alpha chosen by one-step in-sample error."""
    best_level, best_sse = y[-1], np.inf
    for alpha in np.linspace(0.1, 1.0, 10):
        level, sse = y[0], 0.0
        for obs in y[1:]:
            sse += (obs - level) ** 2
            level = alpha * obs + (1 - alpha) * level
        if sse < best_sse:
            best_level, best_sse = level, sse
    return np.repeat(best_level, h)


def pooled_drift(y: np.ndarray, h: int, pooled_step: float = 0.0, **_) -> np.ndarray:
    """Last value plus the average yearly change across all fields."""
    return y[-1] + pooled_step * np.arange(1, h + 1)


METHODS = {
    "naive": naive,
    "drift": drift,
    "mean3": mean3,
    "ses": ses,
    "pooled_drift": pooled_drift,
}


def _pooled_step(train: pd.DataFrame) -> float:
    return float(train.diff().dropna().to_numpy().mean())


def backtest(rates: pd.DataFrame, min_train: int = 3, max_h: int = 2) -> pd.DataFrame:
    """Forecast from every possible origin year and record the errors.

    `rates` is years by fields, as returned by `panel.wide`.
    """
    wide = logit(rates)
    years = wide.index.to_numpy()
    records = []
    for cut in range(min_train, len(years)):
        train = wide.iloc[:cut]
        step = _pooled_step(train)
        horizon = min(max_h, len(years) - cut)
        for field in wide.columns:
            y = train[field].to_numpy()
            for name, fn in METHODS.items():
                pred = fn(y, horizon, pooled_step=step)
                for h in range(1, horizon + 1):
                    actual = wide[field].iloc[cut + h - 1]
                    records.append(
                        {
                            "method": name,
                            "field": field,
                            "origin": int(years[cut - 1]),
                            "target": int(years[cut + h - 1]),
                            "h": h,
                            "logit_error": float(actual - pred[h - 1]),
                            "actual": float(inv_logit(actual)),
                            "forecast": float(inv_logit(pred[h - 1])),
                        }
                    )
    out = pd.DataFrame(records)
    out["abs_error_pp"] = (out["actual"] - out["forecast"]).abs() * 100
    out["ape"] = (out["actual"] - out["forecast"]).abs() / out["actual"] * 100
    return out


def accuracy(bt: pd.DataFrame) -> pd.DataFrame:
    """MAE (percentage points), RMSE and MAPE by method and horizon."""
    g = bt.groupby(["method", "h"])
    out = pd.DataFrame(
        {
            "n": g.size(),
            "origins": g["origin"].nunique(),
            "mae_pp": g["abs_error_pp"].mean(),
            "rmse_pp": g["abs_error_pp"].apply(lambda e: float(np.sqrt((e**2).mean()))),
            "mape": g["ape"].mean(),
        }
    )
    return out.reset_index()


def forecast(
    rates: pd.DataFrame,
    bt: pd.DataFrame,
    method: str,
    horizon: int = 2,
    coverage: float = 0.8,
    shock: pd.Series | None = None,
) -> pd.DataFrame:
    """Forecast each field `horizon` years ahead.

    The band is the forecast plus or minus the `coverage` quantile of that
    method's absolute backtest errors (on the logit scale) at the same
    horizon, pooled across fields. `shock`, if given, is a per-field logit
    shift applied to every forecast year (the stress scenario).
    """
    wide = logit(rates)
    step = _pooled_step(wide)
    last_year = int(wide.index.max())
    errors = bt[bt.method == method]
    records = []
    for field in wide.columns:
        pred = METHODS[method](wide[field].to_numpy(), horizon, pooled_step=step)
        if shock is not None:
            pred = pred + float(shock[field])
        for h in range(1, horizon + 1):
            half = errors.loc[errors.h == h, "logit_error"].abs().quantile(coverage)
            records.append(
                {
                    "field": field,
                    "year": last_year + h,
                    "h": h,
                    "forecast": float(inv_logit(pred[h - 1])),
                    "lower": float(inv_logit(pred[h - 1] - half)),
                    "upper": float(inv_logit(pred[h - 1] + half)),
                }
            )
    return pd.DataFrame(records)
