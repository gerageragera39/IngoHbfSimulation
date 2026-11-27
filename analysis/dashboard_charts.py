
"""Consistent Plotly styling for the dashboard's analytical figures."""

from __future__ import annotations

import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from analyze_results import PLATFORMS, TOL, transfer_minutes

COLORS = {"FIXED_DB": "#F5B76B", "GREEDY": "#50D4B1"}
NEUTRAL = "#A6B8D1"
PANEL = "#121D2B"
GRID = "#2A3A4F"
TEXT = "#E9EFF6"
MUTED = "#ABBBD0"
FONT = "Inter, Segoe UI, sans-serif"


def styled(fig, *, height=350, zero=False):
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=PANEL, plot_bgcolor=PANEL,
        font=dict(family=FONT, color=TEXT, size=13), height=height,
        margin=dict(t=20, b=52, l=56, r=24),
        legend=dict(orientation="h", y=1.02, x=0, title_text=""),
        hoverlabel=dict(bgcolor="#203049", bordercolor=GRID, font_color=TEXT),
        colorway=[NEUTRAL, COLORS["GREEDY"], COLORS["FIXED_DB"]],
    )
    fig.update_xaxes(gridcolor=GRID, tickfont_color=MUTED, automargin=True, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, tickfont_color=MUTED, automargin=True, zeroline=False)
    if zero:
        fig.add_hline(y=0, line_color=MUTED, line_dash="dot", line_width=1)
    return fig


def grouped(frame, x, y, *, color="Dispatcher", unit=""):
    fig = px.bar(frame, x=x, y=y, color=color, barmode="group", color_discrete_map=COLORS)
    fig.update_traces(hovertemplate=f"%{{x}}<br>%{{y:,.2f}} {unit}<extra>%{{fullData.name}}</extra>")
    return styled(fig)


def distribution(frame, value, *, kind="box"):
    if kind == "box":
        fig = px.box(frame, x="Dispatcher", y=value, color="Dispatcher",
                     color_discrete_map=COLORS, points="outliers")
        fig.update_layout(showlegend=False)
    else:
        fig = px.histogram(frame, x=value, color="Dispatcher" if "Dispatcher" in frame else None,
                           color_discrete_map=COLORS, barmode="overlay", opacity=0.78, nbins=30)
        fig.update_yaxes(title="Observations per bin")
    return styled(fig)


def paired_bars(scenarios, *, percentage=False):
    frame = scenarios.sort_values(["scenario_seed", "scenario_id"])
    saved = frame["delay_saved_min"].to_numpy()
    colors = np.where(saved > TOL, COLORS["GREEDY"],
                      np.where(saved < -TOL, COLORS["FIXED_DB"], NEUTRAL))
    reduction = np.array([value if value != "" else np.nan for value in frame["delay_reduction_pct"]], dtype=float)
    details = frame[["fixed_total_delay_min", "greedy_total_delay_min", "delay_saved_min"]].copy()
    details["Reduction"] = [f"{value:.2f}%" if np.isfinite(value) else "Undefined" for value in reduction]
    fig = go.Figure(go.Bar(
        x=[f"{scenario} · {seed}" for scenario, seed in zip(frame["scenario_id"], frame["scenario_seed"])],
        y=reduction if percentage else saved, marker_color=colors,
        customdata=details,
        hovertemplate=("%{x}<br>Paired saving %{customdata[2]:.2f} min<br>"
                       "Reduction %{customdata[3]}<br>"
                       "FIXED_DB %{customdata[0]:.2f} min<br>"
                       "GREEDY %{customdata[1]:.2f} min<extra></extra>"),
    ))
    fig.update_xaxes(title="Scenario and seed", tickangle=-25, nticks=12)
    fig.update_yaxes(title="Secondary delay reduction (%)" if percentage else "FIXED_DB − GREEDY (min)")
    return styled(fig, zero=True, height=390)


def interval(categories, means, low, high, *, y_title, data=None):
    fig = go.Figure()
    for label, mean, lower, upper, metadata in zip(categories, means, low, high,
                                                   data if data is not None else [""] * len(means)):
        has_interval = lower is not None and upper is not None and np.isfinite(lower) and np.isfinite(upper)
        error = dict(type="data", symmetric=False, array=[upper - mean], arrayminus=[mean - lower],
                     color=NEUTRAL, thickness=1.5, width=8) if has_interval else None
        bounds = f"95% CI [{lower:.2f}, {upper:.2f}] min" if has_interval else "95% CI unavailable"
        fig.add_scatter(x=[label], y=[mean], error_y=error, mode="markers",
                        marker=dict(size=10, color="#D3E0F1"), showlegend=False,
                        hovertemplate=f"%{{x}}<br>Mean %{{y:.2f}} min<br>{bounds}<br>{metadata}<extra></extra>")
    fig.update_yaxes(title=y_title)
    fig.update_xaxes(type="category", tickangle=-18)
    return styled(fig, zero=True, height=380)


def matrix(values, unit, *, policy=None, decimals=2):
    platforms = [f"Gleis {p}" for p in PLATFORMS]
    annotated = [[f"{n:,.{decimals}f}" for n in row] for row in values]
    high = {"FIXED_DB": "#875423", "GREEDY": "#186B61"}.get(policy, "#3A648F")
    fig = go.Figure(go.Heatmap(
        z=values, x=platforms, y=platforms, text=annotated, texttemplate="%{text}",
        xgap=3, ygap=3, colorscale=[[0, "#1A2A3E"], [1, high]],
        zmin=0, zmax=max(1e-10, float(np.max(values))), showscale=False,
        hovertemplate=f"Planned %{{y}} → assigned %{{x}}<br>%{{text}} {unit}<extra></extra>",
    ))
    fig.update_xaxes(title="Assigned platform", side="bottom", showgrid=False)
    fig.update_yaxes(title="Planned platform", autorange="reversed", showgrid=False)
    return styled(fig, height=320)


def assignment_matrix(table, column, policy):
    values = table[table["policy"] == policy].pivot(
        index="planned_platform", columns="assigned_platform", values=column
    ).reindex(index=PLATFORMS, columns=PLATFORMS, fill_value=0).to_numpy()
    total = column == "total_train_count"
    return matrix(values, "trains in total" if total else "trains / scenario",
                  policy=policy, decimals=0 if total else 2)


def walking_matrix(transfer):
    values = [[transfer_minutes(transfer, p, q) for q in PLATFORMS] for p in PLATFORMS]
    return matrix(values, "min walking time")


def gantt(trains, policy):
    g = trains[trains["policy"] == policy]
    fig = go.Figure(go.Bar(
        y=[f"Gleis {p}" for p in g["assigned_platform"]],
        base=g["platform_arrival"], x=g["actual_departure"] - g["platform_arrival"],
        orientation="h", marker=dict(color=COLORS[policy], line=dict(color=PANEL, width=1)),
        customdata=g[["train_id", "route_group", "planned_platform", "assigned_platform",
                      "platform_arrival", "actual_departure", "station_delay_min"]],
        hovertemplate=(
            "Train %{customdata[0]} · %{customdata[1]}<br>"
            "Planned Gleis %{customdata[2]} → assigned Gleis %{customdata[3]}<br>"
            "Actual arrival %{customdata[4]:.2f} min<br>"
            "Actual departure %{customdata[5]:.2f} min<br>"
            "Secondary delay %{customdata[6]:.2f} min<extra></extra>"
        ),
    ))
    fig.update_layout(barmode="overlay", bargap=0.28)
    fig.update_yaxes(categoryorder="array", categoryarray=[f"Gleis {p}" for p in PLATFORMS],
                     autorange="reversed", showgrid=False)
    fig.update_xaxes(title="Simulation time (min)", rangemode="tozero")
    return styled(fig, height=290)


def queues(events):
    fig = px.line(events, x="Simulation time (min)", y="Waiting trains", color="Dispatcher",
                  color_discrete_map=COLORS, line_shape="hv")
    fig.update_yaxes(rangemode="tozero", dtick=1)
    return styled(fig, height=300)
