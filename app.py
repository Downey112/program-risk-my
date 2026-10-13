"""Field Risk dashboard. Run with:  streamlit run app.py"""

from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fieldrisk import forecast as fc
from fieldrisk import index as ix
from fieldrisk import panel as pn

INK, INK_2, RULE = "#14213D", "#52607A", "#D5DDE5"
PLUM, PLUM_PALE = "#7A1F5C", "#F7ECF3"
BLUE, AMBER, CONTEXT = "#1F5FAE", "#C77700", "#9AA6B5"
SERIES = [BLUE, AMBER, "#A8327F", "#12936B"]
BODY_FONT = "Public Sans, system-ui, sans-serif"

COLUMNS = {
    "level": ("Not working", "Not-working rate, 2023-2025 average"),
    "trend": ("Drift from national", "Yearly change in the gap to the national rate, 2020-2025. Above zero means falling behind."),
    "low_skill": ("Below-skilled jobs", "Employed graduates outside managerial, professional and technician jobs, 2024"),
    "low_pay": ("Low pay", "Employed degree holders earning RM2,000 a month or less, 2024"),
    "routine": ("Routine jobs", "Employed graduates in clerical or machine-operator jobs, 2024"),
}
PRESETS = {
    "Equal": dict(level=20, trend=20, low_skill=20, low_pay=20, routine=20),
    "Finding work": dict(level=70, trend=30, low_skill=0, low_pay=0, routine=0),
    "Job quality": dict(level=0, trend=0, low_skill=50, low_pay=50, routine=0),
    "Automation": dict(level=10, trend=10, low_skill=10, low_pay=10, routine=60),
}

st.set_page_config(page_title="Graduate field risk, Malaysia", layout="wide")

CSS = f"""
<style>
.block-container {{ padding-top: 2.6rem; max-width: 1180px; }}
h1 {{ font-size: clamp(2rem, 4.2vw, 3.1rem) !important; line-height: 1.04 !important; letter-spacing: -0.02em; max-width: 22ch; padding-bottom: 0.4rem !important; }}
.lede {{ font-size: 1.08rem; line-height: 1.55; color: {INK_2}; max-width: 62ch; margin: 0 0 1.6rem; }}
.note {{ font-size: 0.9rem; line-height: 1.55; color: {INK_2}; max-width: 72ch; }}

.card-wrap {{ overflow-x: auto; background: #fff; border: 1px solid {RULE}; border-radius: 10px; }}
table.card {{ width: 100%; min-width: 760px; border-collapse: collapse; font-family: {BODY_FONT}; color: {INK}; font-variant-numeric: tabular-nums; }}
table.card th {{ font-size: 0.8rem; font-weight: 600; color: {INK_2}; text-align: left; vertical-align: bottom; padding: 14px 10px 10px; border: 0; border-bottom: 2px solid {INK}; line-height: 1.25; }}
table.card th.num {{ text-align: center; }}
table.card td {{ padding: 0 10px; height: 46px; border: 0; border-bottom: 1px solid {RULE}; font-size: 0.95rem; }}
table.card tr:last-child td {{ border-bottom: 0; }}
table.card td.rank {{ width: 2.2rem; color: {INK_2}; font-weight: 600; padding-left: 16px; }}
table.card th:first-child {{ padding-left: 16px; }}
table.card td.field {{ font-weight: 600; white-space: nowrap; }}
table.card td.index {{ width: 30%; min-width: 190px; }}
.bar {{ display: flex; align-items: center; gap: 10px; }}
.bar i {{ display: block; height: 14px; background: {PLUM}; border-radius: 0 3px 3px 0; }}
.bar b {{ font-weight: 600; font-size: 0.9rem; }}
table.card td.cell {{ padding: 4px; width: 11%; }}
.chip {{ display: block; border-radius: 4px; padding: 9px 4px; text-align: center; font-size: 0.9rem; font-weight: 500; }}
table.card tbody tr:hover td {{ background: #F7F9FB; }}
.legend {{ display: flex; align-items: center; gap: 8px; font-size: 0.82rem; color: {INK_2}; margin: 10px 2px 0; }}
.legend span.ramp {{ width: 120px; height: 8px; border-radius: 4px; background: linear-gradient(90deg, {PLUM_PALE}, {PLUM}); }}

[data-testid="stSidebar"] h2 {{ font-size: 1.15rem !important; }}
button:focus-visible, [role="tab"]:focus-visible {{ outline: 2px solid {PLUM}; outline-offset: 2px; }}
</style>
"""


@st.cache_data
def load():
    ge, old8 = pn.load_ge(), pn.load_old8()
    comp = ix.components(ge, pn.load_jobs(), pn.load_pay())
    rates = pn.wide(ge)
    bt = pd.concat([fc.backtest(rates), fc.backtest(pn.wide(old8))], ignore_index=True)
    shock = ix.downturn_shock(old8, pn.TO_NEC8, list(rates.columns))
    return ge, comp, rates, bt, shock


def tint(score: float) -> tuple[str, str]:
    """Background and text colour for a 0-1 score on the plum ramp."""
    lo = [int(PLUM_PALE[i : i + 2], 16) for i in (1, 3, 5)]
    hi = [int(PLUM[i : i + 2], 16) for i in (1, 3, 5)]
    rgb = [round(a + (b - a) * score) for a, b in zip(lo, hi)]
    return "#{:02x}{:02x}{:02x}".format(*rgb), "#fff" if score > 0.62 else INK


def report_card(risk: pd.Series, comp: pd.DataFrame, score: pd.DataFrame) -> str:
    head = "".join(f'<th class="num" title="{escape(tip)}">{escape(name)}</th>' for name, tip in COLUMNS.values())
    rows = []
    for rank, (field, value) in enumerate(risk.items(), start=1):
        cells = []
        for key in COLUMNS:
            raw = comp.loc[field, key]
            text = f"{raw:+.2f}" if key == "trend" else f"{raw * 100:.0f}%"
            bg, fg = tint(float(score.loc[field, key]))
            cells.append(f'<td class="cell"><span class="chip" style="background:{bg};color:{fg}">{text}</span></td>')
        rows.append(
            f'<tr><td class="rank">{rank}</td><td class="field">{escape(pn.SHORT[field])}</td>'
            f'<td class="index"><div class="bar"><i style="width:{value * 78:.1f}%"></i><b>{value:.2f}</b></div></td>'
            f"{''.join(cells)}</tr>"
        )
    return (
        '<div class="card-wrap"><table class="card"><thead><tr><th></th><th>Field of study</th>'
        f"<th>Risk index</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        '<div class="legend">Safest of the ten<span class="ramp"></span>Riskiest of the ten</div>'
    )


def layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=20, t=40, b=10),
        font=dict(family=BODY_FONT, color=INK, size=14),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#fff",
        legend=dict(orientation="h", y=1.1, x=0),
        hoverlabel=dict(namelength=-1, font_family=BODY_FONT),
    )
    fig.update_xaxes(gridcolor="#E8EDF2", zeroline=False, linecolor=RULE, title_font_color=INK_2)
    fig.update_yaxes(gridcolor="#E8EDF2", zeroline=False, linecolor=RULE, title_font_color=INK_2)
    return fig


def apply_preset(name: str) -> None:
    for key, value in PRESETS[name].items():
        st.session_state[f"w_{key}"] = value


ge, comp, rates, bt, shock = load()
score = ix.scores(comp)
for key, value in PRESETS["Equal"].items():
    st.session_state.setdefault(f"w_{key}", value)

st.markdown(CSS, unsafe_allow_html=True)

with st.sidebar:
    st.header("What counts as risk?")
    st.caption("Start from a preset, then move the sliders. The ranking updates as you go.")
    cols = st.columns(2)
    for i, name in enumerate(PRESETS):
        cols[i % 2].button(name, on_click=apply_preset, args=(name,), width="stretch")
    weights = {k: st.slider(COLUMNS[k][0], 0, 100, step=5, key=f"w_{k}", help=COLUMNS[k][1]) for k in COLUMNS}

st.title("Which fields of study leave Malaysian graduates most exposed?")
st.markdown(
    '<p class="lede">Ten fields, scored on five measures from the Ministry of Higher Education\'s yearly survey of new graduates. '
    "Nearly all graduates find work in every field. What separates the fields is the kind of work, and what it pays.</p>",
    unsafe_allow_html=True,
)

if sum(weights.values()) == 0:
    st.warning("Every weight is at zero. Move at least one slider up, or choose a preset.")
    st.stop()

risk = ix.composite(score, weights).sort_values(ascending=False)
tab_card, tab_trend, tab_forecast, tab_method = st.tabs(["Report card", "Six-year trend", "Next year", "Data and method"])

with tab_card:
    st.markdown(report_card(risk, comp, score), unsafe_allow_html=True)
    st.markdown(
        '<p class="note">The index is the weighted average of the five measures after each is rescaled so the safest field scores 0 and the riskiest 1. '
        "It ranks these ten fields against each other. It does not say any field is failing: in 2025 at least 88% of graduates who wanted work had it, in every field. "
        "Hover a column heading for its definition.</p>",
        unsafe_allow_html=True,
    )

with tab_trend:
    picked = st.multiselect("Fields to compare (up to four)", list(rates.columns), default=list(risk.index[:3]), format_func=pn.SHORT.get, max_selections=4)
    nat = ge[ge.field == "total"].set_index("year")["nw_rate"] * 100
    fig = go.Figure()
    fig.add_scatter(x=nat.index, y=nat, name="All fields", line=dict(color=CONTEXT, width=2, dash="dot"), hovertemplate="%{y:.1f}%")
    for field, color in zip(picked, SERIES):
        fig.add_scatter(
            x=rates.index, y=rates[field] * 100, name=pn.SHORT[field], mode="lines+markers", line=dict(color=color, width=2.5), marker=dict(size=7), hovertemplate="%{y:.1f}%"
        )
    fig.update_yaxes(title="Graduates not working (%)", rangemode="tozero")
    fig.update_xaxes(dtick=1)
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(layout(fig, 440), width="stretch")
    st.markdown(
        '<p class="note">Share of graduates not working, out of those working or looking for work. The series starts in 2020 because the Ministry changed its definition in 2024 '
        "and restated only 2020 to 2023; earlier figures count a wider group as not working and cannot be compared.</p>",
        unsafe_allow_html=True,
    )

with tab_forecast:
    left, right = st.columns([1, 1])
    scenario = left.radio("Scenario", ["No shock", "Repeat of the 2020 downturn"], horizontal=True)
    coverage = right.slider("Width of the uncertainty band (%)", 50, 95, 80, 5)
    stressed = scenario != "No shock"
    out = fc.forecast(rates, bt, "naive", coverage=coverage / 100, shock=shock if stressed else None)
    year = int(out.year.min())
    d = out[out.year == year].set_index("field").loc[risk.index[::-1]]
    now = rates.iloc[-1].loc[d.index] * 100
    names = [pn.SHORT[f] for f in d.index]
    fig = go.Figure()
    fig.add_scatter(
        x=d.forecast * 100,
        y=names,
        mode="markers",
        name=f"{year} forecast and band" + ("" if stressed else f" (same as {int(rates.index[-1])})"),
        marker=dict(color=AMBER if stressed else BLUE, size=11),
        error_x=dict(type="data", symmetric=False, array=(d.upper - d.forecast) * 100, arrayminus=(d.forecast - d.lower) * 100, thickness=2.5, width=0),
        customdata=d[["lower", "upper"]].to_numpy() * 100,
        hovertemplate="%{y}: %{x:.1f}% (%{customdata[0]:.1f} to %{customdata[1]:.1f})<extra></extra>",
    )
    if stressed:
        fig.add_scatter(
            x=now, y=names, mode="markers", name=f"{int(rates.index[-1])} actual", marker=dict(color="#fff", size=8, line=dict(color=INK, width=2)), hovertemplate="%{y}: %{x:.1f}%<extra></extra>"
        )
    fig.update_layout(showlegend=True)
    fig.update_xaxes(title="Graduates not working (%)", rangemode="tozero")
    st.plotly_chart(layout(fig, 470), width="stretch")
    st.markdown(
        '<p class="note">With six yearly figures per field, the rule "next year equals this year" missed by less than any trend method when tested on past years, '
        "so that is the forecast. The band shows how far that rule has missed before, including across the 2020 downturn and the 2022 recovery. "
        "The downturn scenario adds each field's 2019 to 2020 rise again; Education's rate fell that year, so it moves the other way.</p>",
        unsafe_allow_html=True,
    )

with tab_method:
    st.markdown(
        """
#### Where the figures come from

Graduate Tracer Study (SKPG) report 2024, Tables 8h, 4k and 4o, and *Statistik Pendidikan Tinggi* 2015-2025, chapter 7.
Malaysian citizens, certificate to PhD, surveyed around graduation.

#### What this cannot show

- Individual programmes or universities. Results are published for ten broad fields only.
- Oversupply. There is no public count of vacancies by field of study.
- Automation risk. "Routine jobs" is a stand-in: the share of graduates in clerical or machine-operator work.
- Anything past the first job. Outcomes are measured around graduation.

Code, tests and the full write-up: [github.com/Downey112/program-risk-my](https://github.com/Downey112/program-risk-my)

#### Graduates not working, by field and year (%)
"""
    )
    st.dataframe((rates * 100).round(1).rename(columns=pn.SHORT), width="stretch")
