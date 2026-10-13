"""Field Risk dashboard. Run with:  streamlit run app.py"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fieldrisk import forecast as fc
from fieldrisk import index as ix
from fieldrisk import panel as pn

BLUE, ORANGE, CONTEXT, GRID = "#2a78d6", "#eb6834", "#b5b4ae", "#e4e3df"
SLIDER_LABELS = {
    "level": "Not working (2023-2025)",
    "trend": "Trend against national rate",
    "low_skill": "Jobs below skilled level",
    "low_pay": "Low pay, degree holders",
    "routine": "Clerical / operator jobs",
}

st.set_page_config(page_title="Graduate field risk, Malaysia", layout="wide")


@st.cache_data
def load():
    ge, old8 = pn.load_ge(), pn.load_old8()
    comp = ix.components(ge, pn.load_jobs(), pn.load_pay())
    rates = pn.wide(ge)
    bt = pd.concat([fc.backtest(rates), fc.backtest(pn.wide(old8))], ignore_index=True)
    shock = ix.downturn_shock(old8, pn.TO_NEC8, list(rates.columns))
    return ge, comp, rates, bt, shock


def layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.08, x=0),
        hoverlabel=dict(namelength=-1),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


ge, comp, rates, bt, shock = load()
score = ix.scores(comp)

st.title("Which fields of study leave Malaysian graduates most exposed?")
st.caption(
    "Ten fields of study, from the Ministry of Higher Education's Graduate Tracer Study. "
    "Rates use the Ministry's 2024 definition: graduates not working as a share of those working or looking for work."
)

with st.sidebar:
    st.header("Index weights")
    st.caption("Each indicator is rescaled so the safest field scores 0 and the riskiest 1. Weights are normalised to sum to 1.")
    weights = {k: st.slider(SLIDER_LABELS[k], 0, 100, 20, 5, help=ix.COMPONENTS[k]) for k in ix.COMPONENTS}
    st.header("Forecast")
    scenario = st.radio("Scenario", ["Baseline", "Downturn"], help="Downturn repeats each field's 2019 to 2020 rise in the not-working rate.")
    coverage = st.slider("Band coverage (%)", 50, 95, 80, 5)

if sum(weights.values()) == 0:
    st.warning("Set at least one weight above zero.")
    st.stop()

risk = ix.composite(score, weights).sort_values()
tab_index, tab_trend, tab_forecast, tab_data = st.tabs(["Risk index", "Trends", "Forecast", "Data and method"])

with tab_index:
    left, right = st.columns([1.1, 1])
    with left:
        fig = go.Figure(
            go.Bar(
                x=risk.values,
                y=[pn.SHORT[f] for f in risk.index],
                orientation="h",
                marker_color=BLUE,
                text=[f"{v:.2f}" for v in risk.values],
                textposition="outside",
                hovertemplate="%{y}: %{x:.2f}<extra></extra>",
            )
        )
        fig.update_xaxes(range=[0, 1.08], title="Field Risk Index (0 = safest on every indicator, 1 = riskiest)")
        st.plotly_chart(layout(fig, 430), width="stretch")
    with right:
        order = risk.index[::-1]
        display = comp.loc[order].copy()
        display.index = [pn.SHORT[f] for f in order]
        display.columns = [SLIDER_LABELS[c] for c in display.columns]
        pct = [c for c in display.columns if c != SLIDER_LABELS["trend"]]
        display[pct] = display[pct] * 100
        st.dataframe(
            display.style.format("{:.1f}%", subset=pct).format("{:+.3f}", subset=[SLIDER_LABELS["trend"]]).background_gradient(cmap="Blues", axis=0),
            width="stretch",
            height=430,
        )
    st.caption(
        "Trend is the yearly change in the field's gap to the national rate on the logit scale; positive means the field is falling behind. "
        "Job and pay indicators are for 2024 only. A high score means a field ranks badly among these ten, not that it is failing: "
        "every field had at least 88% of its labour-force graduates in work in 2025."
    )

with tab_trend:
    picked = st.multiselect("Fields", list(rates.columns), default=list(risk.index[::-1][:3]), format_func=pn.SHORT.get, max_selections=4)
    nat = ge[ge.field == "total"].set_index("year")["nw_rate"] * 100
    fig = go.Figure()
    fig.add_scatter(x=nat.index, y=nat, name="All fields", line=dict(color=CONTEXT, width=2, dash="dot"))
    for field, color in zip(picked, [BLUE, ORANGE, "#1baf7a", "#eda100"]):
        fig.add_scatter(x=rates.index, y=rates[field] * 100, name=pn.SHORT[field], line=dict(color=color, width=2), mode="lines+markers")
    fig.update_yaxes(title="Graduates not working (%)", rangemode="tozero")
    fig.update_xaxes(dtick=1)
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(layout(fig, 430), width="stretch")
    st.caption("Figures before 2020 exist only on an earlier, wider definition of 'not working' and are not comparable; see the README.")

with tab_forecast:
    out = fc.forecast(rates, bt, "naive", coverage=coverage / 100, shock=shock if scenario == "Downturn" else None)
    year = int(out.year.min())
    d = out[out.year == year].set_index("field").loc[risk.index]
    fig = go.Figure(
        go.Scatter(
            x=d.forecast * 100,
            y=[pn.SHORT[f] for f in d.index],
            mode="markers",
            marker=dict(color=ORANGE if scenario == "Downturn" else BLUE, size=10),
            error_x=dict(type="data", symmetric=False, array=(d.upper - d.forecast) * 100, arrayminus=(d.forecast - d.lower) * 100, thickness=2, width=0),
            customdata=d[["lower", "upper"]].to_numpy() * 100,
            hovertemplate="%{y}: %{x:.1f}% (%{customdata[0]:.1f} to %{customdata[1]:.1f})<extra></extra>",
        )
    )
    fig.update_xaxes(title=f"Forecast share of graduates not working in {year} (%), with {coverage}% band", rangemode="tozero")
    st.plotly_chart(layout(fig, 430), width="stretch")
    st.caption(
        "With six yearly observations per field, 'next year equals this year' had the lowest backtest error on this series, "
        "so that is the forecast. The band comes from how far that rule missed in the past, including across the 2020 downturn and the 2022 recovery."
    )

with tab_data:
    st.markdown(
        """
**Sources.** Graduate Tracer Study (SKPG) report 2024, Tables 8h, 4k and 4o; *Statistik Pendidikan Tinggi* 2015-2025, chapter 7. Malaysian citizens only.

**What this cannot show.** The published data stops at ten broad fields. Individual programmes, universities within a field,
automation risk scores and job vacancies by field are not public, so the 'routine jobs' indicator is only a stand-in for automation exposure
and there is no oversupply measure.
"""
    )
    st.dataframe((rates * 100).round(1).rename(columns=pn.SHORT), width="stretch")
