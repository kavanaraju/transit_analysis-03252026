"""
Transit Network Resilience to Gas Price Shocks
Kavana | LinkedIn post analysis
--------------------------------------
Charts:
  1. Time series — national UPT + gas prices 2005–2026, shock windows annotated
  2. Scatter — agency 2019 capacity vs 2022 ridership response, SEPTA highlighted
  3. Bar — top 30 agencies by capacity, colored by 2022 response, SEPTA highlighted
"""

import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── PATHS ─────────────────────────────────────────────────────────────────────
NTD_PATH = "/mnt/user-data/uploads/ntd_ridership.xlsx"
EIA_PATH = "/mnt/user-data/uploads/eia_gas_prices.xls"
OUT_PATH = "/mnt/user-data/outputs/transit_shock_analysis.html"

# ── 1. LOAD & CLEAN EIA GAS PRICES ───────────────────────────────────────────
print("Loading EIA gas prices...")
gas = pd.read_excel(EIA_PATH, engine="xlrd", sheet_name="Data 1", skiprows=2)
gas.columns = ["date", "price"]
gas["date"] = pd.to_datetime(gas["date"])
gas = gas.dropna().reset_index(drop=True)

# Monthly average for merging with NTD
gas_monthly = gas.copy()
gas_monthly["month"] = gas_monthly["date"].dt.to_period("M")
gas_monthly = (
    gas_monthly.groupby("month")["price"]
    .mean()
    .reset_index()
)
gas_monthly["date"] = gas_monthly["month"].dt.to_timestamp()

# ── 2. LOAD & MELT NTD ───────────────────────────────────────────────────────
print("Loading NTD data (this takes ~30s)...")
upt_raw = pd.read_excel(NTD_PATH, sheet_name="UPT")
vrh_raw = pd.read_excel(NTD_PATH, sheet_name="VRH")

META = ["NTD ID", "Agency", "UZA Name", "Mode", "TOS"]
DATE_COLS = [c for c in upt_raw.columns if isinstance(c, str) and re.match(r"^\d{1,2}/\d{4}$", c)]


def melt_ntd(df, value_name):
    melted = df[META + DATE_COLS].melt(
        id_vars=META, var_name="month_str", value_name=value_name
    )
    melted["date"] = pd.to_datetime(melted["month_str"], format="%m/%Y")
    return melted.drop(columns="month_str")


upt = melt_ntd(upt_raw, "UPT")
vrh = melt_ntd(vrh_raw, "VRH")
ntd = upt.merge(vrh, on=META + ["date"], how="left")

# ── 3. AGGREGATE TO AGENCY-MONTH ──────────────────────────────────────────────
print("Aggregating...")
agency_monthly = (
    ntd.groupby(["NTD ID", "Agency", "UZA Name", "date"])[["UPT", "VRH"]]
    .sum(min_count=1)
    .reset_index()
)

# ── 4. NATIONAL MONTHLY ───────────────────────────────────────────────────────
national = (
    agency_monthly.groupby("date")[["UPT", "VRH"]]
    .sum()
    .reset_index()
)
# Clip to 2005 onward for cleaner chart
national = national[national["date"] >= "2005-01-01"]

# ── 5. CAPACITY INDEX (2019 avg monthly VRH, pre-COVID) ───────────────────────
capacity = (
    agency_monthly[agency_monthly["date"].dt.year == 2019]
    .groupby(["NTD ID", "Agency", "UZA Name"])["VRH"]
    .mean()
    .reset_index()
    .rename(columns={"VRH": "cap_vrh"})
)

# ── 6. 2022 SHOCK RESPONSE ────────────────────────────────────────────────────
# Ukraine war: gas prices rose sharply Feb–Jun 2022
# Baseline = Jan–Feb 2022, shock window = Mar–Aug 2022

def shock_response(df, b_start, b_end, s_start, s_end):
    baseline = (
        df[(df["date"] >= b_start) & (df["date"] <= b_end)]
        .groupby(["NTD ID", "Agency"])["UPT"]
        .mean()
        .reset_index()
        .rename(columns={"UPT": "upt_baseline"})
    )
    shock = (
        df[(df["date"] >= s_start) & (df["date"] <= s_end)]
        .groupby(["NTD ID", "Agency"])["UPT"]
        .mean()
        .reset_index()
        .rename(columns={"UPT": "upt_shock"})
    )
    merged = baseline.merge(shock, on=["NTD ID", "Agency"])
    merged["pct_change"] = (
        (merged["upt_shock"] - merged["upt_baseline"]) / merged["upt_baseline"] * 100
    )
    return merged


response_2022 = shock_response(
    agency_monthly,
    "2022-01-01", "2022-02-28",
    "2022-03-01", "2022-08-31",
)

# Merge with capacity
scatter_df = response_2022.merge(capacity, on=["NTD ID", "Agency"])
# Keep agencies with meaningful service and plausible response
scatter_df = scatter_df[
    (scatter_df["cap_vrh"] > 500) &
    (scatter_df["pct_change"].between(-60, 120))
].copy()

# SEPTA flag
SEPTA_ID = 30019
scatter_df["is_septa"] = scatter_df["NTD ID"] == SEPTA_ID
septa_row = scatter_df[scatter_df["is_septa"]].iloc[0]

# ── 7. BAR CHART DATA ─────────────────────────────────────────────────────────
# Top 30 agencies by 2019 capacity
bar_df = scatter_df.nlargest(30, "cap_vrh").sort_values("pct_change")

# ── 8. BUILD FIGURE ───────────────────────────────────────────────────────────
print("Building figure...")

fig = make_subplots(
    rows=2, cols=2,
    row_heights=[0.45, 0.55],
    column_widths=[0.55, 0.45],
    specs=[[{"colspan": 2}, None],
           [{"type": "xy"}, {"type": "xy"}]],
    subplot_titles=[
        "National Transit Ridership & Gas Prices (2005–2026)",
        "Network Capacity vs. 2022 Ridership Response",
        "2022 Shock Response — Top 30 Agencies by Capacity",
    ],
    vertical_spacing=0.14,
    horizontal_spacing=0.10,
)

# ── PALETTE ───────────────────────────────────────────────────────────────────
BG        = "#0f1117"
CARD      = "#1a1d27"
GRID      = "#2a2d3a"
TEXT      = "#e2e8f0"
SUBTEXT   = "#8892a4"
ACCENT1   = "#6366f1"   # indigo — gas price / primary
ACCENT2   = "#10b981"   # emerald — ridership
ORANGE    = "#f97316"   # SEPTA highlight
RED       = "#ef4444"
YELLOW    = "#fbbf24"

# ────────────────────────────────────────────────────────────────────────────
# PANEL 1 — TIME SERIES
# ────────────────────────────────────────────────────────────────────────────

# Gas price line
fig.add_trace(
    go.Scatter(
        x=gas[gas["date"] >= "2005-01-01"]["date"],
        y=gas[gas["date"] >= "2005-01-01"]["price"],
        name="Gas price ($/gal)",
        line=dict(color=ACCENT1, width=1.8),
        yaxis="y2",
        hovertemplate="%{x|%b %Y}<br>$%{y:.2f}/gal<extra></extra>",
    ),
    row=1, col=1,
)

# National UPT (in billions for readability)
fig.add_trace(
    go.Scatter(
        x=national["date"],
        y=national["UPT"] / 1e9,
        name="National ridership (B trips/mo)",
        line=dict(color=ACCENT2, width=2),
        fill="tozeroy",
        fillcolor="rgba(16,185,129,0.08)",
        hovertemplate="%{x|%b %Y}<br>%{y:.2f}B trips<extra></extra>",
    ),
    row=1, col=1,
)

# Shock window shading helper
def add_vrect(fig, x0, x1, label, color, row, col):
    fig.add_vrect(
        x0=x0, x1=x1,
        fillcolor=color, opacity=0.12, line_width=0,
        row=row, col=col,
    )
    fig.add_annotation(
        x=pd.Timestamp(x0) + (pd.Timestamp(x1) - pd.Timestamp(x0)) / 2,
        y=1.0, yref="paper",
        text=label, showarrow=False,
        font=dict(size=9, color=SUBTEXT),
        xanchor="center",
    )

add_vrect(fig, "2007-11-01", "2009-03-01", "2008 shock", YELLOW, 1, 1)
add_vrect(fig, "2022-02-01", "2022-09-01", "2022 shock", RED, 1, 1)

# Annotate current crisis
fig.add_vline(
    x="2026-02-28", line_dash="dash", line_color=RED,
    line_width=1.5, row=1, col=1,
)
fig.add_annotation(
    x="2026-02-28", y=0.85, yref="paper",
    text="Iran war ↑40%+", showarrow=False,
    font=dict(size=9, color=RED), xanchor="left", xshift=6,
)

# ────────────────────────────────────────────────────────────────────────────
# PANEL 2 — SCATTER
# ────────────────────────────────────────────────────────────────────────────

non_septa = scatter_df[~scatter_df["is_septa"]]

fig.add_trace(
    go.Scatter(
        x=non_septa["cap_vrh"],
        y=non_septa["pct_change"],
        mode="markers",
        name="Transit agency",
        marker=dict(
            size=7,
            color=non_septa["pct_change"],
            colorscale=[[0, "#ef4444"], [0.5, "#fbbf24"], [1, "#10b981"]],
            cmin=-30, cmax=60,
            opacity=0.7,
            line=dict(width=0),
            showscale=True,
            colorbar=dict(
                title=dict(text="% change", font=dict(size=10, color=SUBTEXT)),
                tickfont=dict(size=9, color=SUBTEXT),
                x=1.02, thickness=10, len=0.45, y=0.25,
            ),
        ),
        customdata=non_septa[["Agency", "UZA Name"]],
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "%{customdata[1]}<br>"
            "Capacity: %{x:,.0f} VRH/mo<br>"
            "Ridership change: %{y:.1f}%<extra></extra>"
        ),
    ),
    row=2, col=1,
)

# SEPTA highlighted
fig.add_trace(
    go.Scatter(
        x=[septa_row["cap_vrh"]],
        y=[septa_row["pct_change"]],
        mode="markers+text",
        name="SEPTA",
        marker=dict(size=14, color=ORANGE, symbol="diamond", line=dict(width=1.5, color="white")),
        text=["SEPTA"],
        textposition="top right",
        textfont=dict(size=10, color=ORANGE),
        hovertemplate=(
            "<b>SEPTA</b><br>"
            f"Capacity: {septa_row['cap_vrh']:,.0f} VRH/mo<br>"
            f"2022 response: {septa_row['pct_change']:.1f}%<extra></extra>"
        ),
    ),
    row=2, col=1,
)

# Zero reference line
fig.add_hline(y=0, line_dash="dot", line_color=GRID, line_width=1, row=2, col=1)

# ────────────────────────────────────────────────────────────────────────────
# PANEL 3 — BAR CHART
# ────────────────────────────────────────────────────────────────────────────

bar_colors = [
    ORANGE if ntd_id == SEPTA_ID else
    ACCENT2 if pct > 5 else
    RED if pct < -5 else
    YELLOW
    for ntd_id, pct in zip(bar_df["NTD ID"], bar_df["pct_change"])
]

# Shorten long agency names for display
def shorten(name, maxlen=28):
    return name if len(name) <= maxlen else name[:maxlen-1] + "…"

bar_df = bar_df.copy()
bar_df["short_name"] = bar_df["Agency"].apply(shorten)

fig.add_trace(
    go.Bar(
        x=bar_df["pct_change"],
        y=bar_df["short_name"],
        orientation="h",
        marker_color=bar_colors,
        marker_line_width=0,
        customdata=bar_df[["Agency", "cap_vrh"]],
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Capacity: %{customdata[1]:,.0f} VRH/mo<br>"
            "2022 response: %{x:.1f}%<extra></extra>"
        ),
        name="",
        showlegend=False,
    ),
    row=2, col=2,
)

fig.add_vline(x=0, line_dash="dot", line_color=GRID, line_width=1, row=2, col=2)

# ── LAYOUT ────────────────────────────────────────────────────────────────────

fig.update_layout(
    title=dict(
        text="<b>Will the gas price shock drive people to transit?</b><br>"
             "<span style='font-size:13px;color:#8892a4'>"
             "Historical ridership responses suggest the answer depends less on gas prices "
             "and more on whether the network exists to absorb demand."
             "</span>",
        font=dict(size=18, color=TEXT),
        x=0.01, xanchor="left",
        y=0.98,
    ),
    paper_bgcolor=BG,
    plot_bgcolor=CARD,
    font=dict(family="Inter, Arial, sans-serif", color=TEXT),
    height=780,
    margin=dict(t=100, b=60, l=60, r=80),
    legend=dict(
        orientation="h",
        x=0.01, y=1.09,
        font=dict(size=11),
        bgcolor="rgba(0,0,0,0)",
    ),
    hovermode="closest",
)

# Axes — panel 1
fig.update_xaxes(
    row=1, col=1,
    showgrid=True, gridcolor=GRID, gridwidth=1,
    tickfont=dict(size=10, color=SUBTEXT),
    showline=False, zeroline=False,
    range=["2005-01-01", "2026-06-01"],
)
fig.update_yaxes(
    row=1, col=1,
    title_text="Ridership (billion trips/mo)",
    title_font=dict(size=11, color=SUBTEXT),
    showgrid=True, gridcolor=GRID,
    tickfont=dict(size=10, color=SUBTEXT),
    zeroline=False,
)

# Secondary y-axis for gas price
fig.update_layout(
    yaxis2=dict(
        title="Gas price ($/gal)",
        title_font=dict(size=11, color=ACCENT1),
        overlaying="y",
        side="right",
        showgrid=False,
        tickfont=dict(size=10, color=ACCENT1),
        zeroline=False,
    )
)

# Axes — panel 2
fig.update_xaxes(
    row=2, col=1,
    type="log",
    title_text="2019 avg monthly vehicle revenue hours (log scale)",
    title_font=dict(size=10, color=SUBTEXT),
    showgrid=True, gridcolor=GRID,
    tickfont=dict(size=9, color=SUBTEXT),
    zeroline=False,
)
fig.update_yaxes(
    row=2, col=1,
    title_text="UPT change, Feb → Mar–Aug 2022 (%)",
    title_font=dict(size=10, color=SUBTEXT),
    showgrid=True, gridcolor=GRID,
    tickfont=dict(size=9, color=SUBTEXT),
    zeroline=False,
)

# Axes — panel 3
fig.update_xaxes(
    row=2, col=2,
    title_text="UPT change (%)",
    title_font=dict(size=10, color=SUBTEXT),
    showgrid=True, gridcolor=GRID,
    tickfont=dict(size=9, color=SUBTEXT),
    zeroline=False,
)
fig.update_yaxes(
    row=2, col=2,
    showgrid=False,
    tickfont=dict(size=9, color=SUBTEXT),
    automargin=True,
)

# Subplot title styling
for ann in fig.layout.annotations:
    if ann.text in [
        "National Transit Ridership & Gas Prices (2005–2026)",
        "Network Capacity vs. 2022 Ridership Response",
        "2022 Shock Response — Top 30 Agencies by Capacity",
    ]:
        ann.font.size = 12
        ann.font.color = TEXT

# ── CAPTION ───────────────────────────────────────────────────────────────────
fig.add_annotation(
    text=(
        "Source: FTA National Transit Database (Monthly Module, Jan 2026 release) · "
        "EIA Weekly Retail Gasoline Prices · "
        "Capacity = avg monthly vehicle revenue hours 2019 (pre-COVID baseline) · "
        "2022 shock window: Mar–Aug 2022 vs Jan–Feb baseline"
    ),
    xref="paper", yref="paper",
    x=0.0, y=-0.07,
    showarrow=False,
    font=dict(size=8, color=SUBTEXT),
    xanchor="left",
)

# ── EXPORT ────────────────────────────────────────────────────────────────────
print("Saving...")
fig.write_html(
    OUT_PATH,
    include_plotlyjs="cdn",
    config={"displayModeBar": True, "responsive": True},
)
print(f"Done → {OUT_PATH}")
print(f"\nKey stats:")
print(f"  SEPTA 2022 response: {septa_row['pct_change']:.1f}%")
print(f"  SEPTA 2019 capacity: {septa_row['cap_vrh']:,.0f} VRH/mo")
print(f"  Agencies in scatter: {len(scatter_df)}")
print(f"  Gas price data through: {gas['date'].max().strftime('%b %d, %Y')}")
