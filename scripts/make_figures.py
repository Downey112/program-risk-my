"""Draw the report figures from results/ into figures/. Run scripts/analyse.py first."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fieldrisk.index import COMPONENTS  # noqa: E402
from fieldrisk.panel import SHORT  # noqa: E402

RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
CONTEXT = "#b5b4ae"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
BLUES = LinearSegmentedColormap.from_list("blues", ["#eef4fc", "#cde2fb", "#6da7ec", "#256abf", "#0d366b"])

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "axes.edgecolor": GRID,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
    }
)

SCORE_LABELS = {
    "level": "Not\nworking",
    "trend": "Trend vs\nnational",
    "low_skill": "Below-skilled\njobs",
    "low_pay": "Low pay\n(degree)",
    "routine": "Routine\njobs",
}


def save(fig: plt.Figure, name: str) -> None:
    FIGURES.mkdir(exist_ok=True)
    fig.savefig(FIGURES / name, dpi=160, bbox_inches="tight")
    plt.close(fig)


def national() -> None:
    nat = pd.read_csv(RESULTS / "national.csv").set_index("year")
    old = nat["nw_rate"].dropna() * 100
    new = nat["nw_rate_2024_definition"].dropna() * 100
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(old.index, old, color=ORANGE, lw=2, marker="o", ms=4)
    ax.plot(new.index, new, color=BLUE, lw=2, marker="o", ms=4)
    ax.annotate("Earlier tables", (2016, old[2016]), xytext=(8, 8), textcoords="offset points", color=INK)
    ax.annotate("2024 definition", (2022, new[2022]), xytext=(-6, -18), textcoords="offset points", color=INK, ha="right")
    for series in (old, new):
        ax.annotate(f"{series.iloc[-1]:.1f}%", (series.index[-1], series.iloc[-1]), xytext=(7, -3), textcoords="offset points", color=INK)
    ax.set_ylim(0, 37)
    ax.set_xticks(range(2014, 2026))
    ax.set_ylabel("Graduates not working, % of those\nworking or looking for work")
    ax.set_title("The 2024 redefinition lowered the rate by about four points")
    save(fig, "national_two_definitions.png")


def fields() -> None:
    panel = pd.read_csv(RESULTS / "field_panel.csv")
    order = pd.read_csv(RESULTS / "risk_index.csv")["field"].tolist()
    nat = panel[panel.field == "total"].set_index("year")["nw_rate"] * 100
    fig, axes = plt.subplots(2, 5, figsize=(13, 5.2), sharex=True, sharey=True)
    for ax, field in zip(axes.flat, order, strict=True):
        s = panel[panel.field == field].set_index("year")["nw_rate"] * 100
        ax.plot(nat.index, nat, color=CONTEXT, lw=1.5)
        ax.plot(s.index, s, color=BLUE, lw=2)
        ax.scatter([s.index[-1]], [s.iloc[-1]], color=BLUE, s=22, zorder=3)
        ax.annotate(f"{s.iloc[-1]:.1f}%", (s.index[-1], s.iloc[-1]), xytext=(-2, 8), textcoords="offset points", ha="right", color=INK)
        ax.set_title(SHORT[field], fontsize=10.5)
        ax.set_ylim(0, 26)
        ax.set_xticks([2020, 2025])
    axes[0, 0].plot([], [], color=BLUE, lw=2, label="Field")
    axes[0, 0].plot([], [], color=CONTEXT, lw=1.5, label="All fields")
    fig.legend(loc="upper right", ncol=2, frameon=False, bbox_to_anchor=(0.985, 1.0))
    fig.suptitle("Graduates not working by field, 2020-2025 (%, 2024 definition; riskiest first)", x=0.01, ha="left", fontweight="bold", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save(fig, "field_trends.png")


def risk() -> None:
    table = pd.read_csv(RESULTS / "risk_index.csv").set_index("field").iloc[::-1]
    fig, (ax, hm) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.05, 1], "wspace": 0.04})
    y = range(len(table))
    ax.barh(y, table["risk_index"], height=0.62, color=BLUE)
    for i, (_, row) in enumerate(table.iterrows()):
        ax.text(row.risk_index + 0.012, i, f"{row.risk_index:.2f}   rank {int(row.rank_p05)}-{int(row.rank_p95)}", va="center", color=INK, fontsize=9.5)
    ax.set_yticks(list(y), [SHORT[f] for f in table.index])
    ax.tick_params(axis="y", labelcolor=INK)
    ax.set_xlim(0, 1.08)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel("Field Risk Index, equal weights (0 = safest on every indicator, 1 = riskiest)")
    ax.set_title("Field Risk Index, with rank range under random weights")

    cols = list(COMPONENTS)
    scores = table[[f"score_{c}" for c in cols]].to_numpy()
    hm.imshow(scores, cmap=BLUES, vmin=0, vmax=1, aspect="auto", origin="lower")
    raw = table[[f"raw_{c}" for c in cols]].to_numpy()
    for i in range(scores.shape[0]):
        for j, c in enumerate(cols):
            text = f"{raw[i, j]:+.2f}" if c == "trend" else f"{raw[i, j] * 100:.0f}%"
            hm.text(j, i, text, ha="center", va="center", fontsize=9, color="white" if scores[i, j] > 0.6 else INK)
    hm.set_xticks(range(len(cols)), [SCORE_LABELS[c] for c in cols])
    hm.set_yticks([])
    hm.xaxis.tick_top()
    hm.grid(False)
    for spine in hm.spines.values():
        spine.set_visible(False)
    hm.set_xticks([x - 0.5 for x in range(1, len(cols))], minor=True)
    hm.set_yticks([v - 0.5 for v in range(1, len(table))], minor=True)
    hm.grid(which="minor", color=SURFACE, linewidth=2)
    hm.tick_params(which="minor", length=0)
    hm.set_xlabel("Indicator values; darker = riskier among the ten fields")
    save(fig, "risk_index.png")


def forecasts() -> None:
    fc = pd.read_csv(RESULTS / "forecasts.csv")
    order = pd.read_csv(RESULTS / "risk_index.csv")["field"].tolist()[::-1]
    year = fc["year"].min()
    fc = fc[fc.year == year]
    fig, ax = plt.subplots(figsize=(8.5, 5))
    for scenario, color, dy in (("baseline", BLUE, 0.16), ("downturn", ORANGE, -0.16)):
        d = fc[fc.scenario == scenario].set_index("field").loc[order]
        ys = [i + dy for i in range(len(order))]
        ax.hlines(ys, d.lower * 100, d.upper * 100, color=color, lw=2, alpha=0.45)
        ax.scatter(d.forecast * 100, ys, color=color, s=38, zorder=3, edgecolor=SURFACE, linewidth=1.5, label=f"{scenario.capitalize()} forecast, 80% band")
    ax.set_yticks(range(len(order)), [SHORT[f] for f in order])
    ax.tick_params(axis="y", labelcolor=INK)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlim(0, 21)
    ax.set_xlabel("Graduates not working, % of those working or looking for work")
    ax.set_title(f"{year} forecast by field: no change expected, with wide bands")
    ax.legend(frameon=False, loc="lower right")
    save(fig, "forecast.png")


def main() -> None:
    national()
    fields()
    risk()
    forecasts()
    print(f"wrote figures to {FIGURES}")


if __name__ == "__main__":
    main()
