"""Interactive, offline replay of the existing Ingolstadt Hbf AnyLogic CSV exports.

Run from repository root:
    python -m streamlit run analysis/station_dashboard.py
"""
from __future__ import annotations

import html
import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from station_dashboard_core import (
    PLATFORMS, ROUTE_COLORS, classify, discover_pairs, final_metrics,
    load_pair, metrics_now, timeline_counts,
)

st.set_page_config(
    page_title="Ingolstadt Hbf | Dispatch Replay",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLOR_FIXED = "#E4A157"
COLOR_GREEDY = "#47D6B1"
BG = "#0C1423"
PANEL_BG = "#111C2D"
WHITE = "#EAF1FA"
MUTED = "#9BAAC0"

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {background: #0B1422;}
[data-testid="stSidebar"] {background: #101B2D;}
[data-testid="stHeader"] {background: rgba(11,20,34,.85);}
h1, h2, h3, .stMarkdown {color: #EAF1FA;}
[data-testid="stMetric"] {
    background: #142137; border: 1px solid #273B54; border-radius: 12px;
    padding: 14px 16px; min-height: 103px;
}
[data-testid="stMetricLabel"] {color:#A8B6CB;}
[data-testid="stMetricValue"] {color:#F4F8FF;}
.hero {
    padding:20px 24px;border:1px solid #2A3E59;border-radius:17px;
    background:linear-gradient(115deg,#172942,#122034 62%,#132D37);
    margin-bottom:12px;
}
.kicker {font-size:12px;color:#54DFC2;text-transform:uppercase;letter-spacing:2px;font-weight:700;}
.headline {font-size:32px;font-weight:800;color:#F5FAFF;letter-spacing:-.8px;}
.subline {font-size:14px;color:#ACBDD1;}
.small-card {padding:12px 16px; background:#152339; border:1px solid #2B4059; border-radius:12px;}
.small-card strong {color:#F4F9FF;}
.small-card span {color:#ADC0D5;font-size:12px;}
</style>
""", unsafe_allow_html=True)


def fmt(value: float) -> str:
    return f"{value:,.1f}".replace(",", " ").replace(".", ",")


def tracks_figure(df: pd.DataFrame, states: dict, t: float, policy: str) -> go.Figure:
    """A schematic 4-track station, not a geographically correct plan."""
    active = {int(x["assigned_platform"]): x for _, x in states["platform"].iterrows()}
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, y0=0, x1=100, y1=6.0,
                  fillcolor=PANEL_BG, line=dict(width=0), layer="below")
    ypos = {2: 5.0, 3: 3.75, 4: 2.5, 5: 1.25}
    for p in PLATFORMS:
        y = ypos[p]
        # Platform surface and railway sleepers; schematic only.
        fig.add_shape(type="rect", x0=30, x1=96, y0=y + .32, y1=y + .52,
                      fillcolor="#283A51", line=dict(color="#3D536A", width=.7))
        for i in range(23, 96, 6):
            fig.add_shape(type="line", x0=i, x1=i, y0=y - .23, y1=y + .22,
                          line=dict(color="#3A4B60", width=3))
        for dy in (-.15, .15):
            fig.add_shape(type="line", x0=17, x1=97, y0=y + dy, y1=y + dy,
                          line=dict(color="#91A5BD", width=2.4))
        fig.add_annotation(x=1.5, y=y, xanchor="left", text=f"<b>GLEIS {p}</b>",
                           showarrow=False, font=dict(size=13, color=WHITE))
        if p in active:
            train = active[p]
            color = ROUTE_COLORS.get(str(train["route_group"]), "#54BFE7")
            fig.add_shape(type="rect", x0=39, x1=87, y0=y - .27, y1=y + .27,
                          fillcolor=color, opacity=.96,
                          line=dict(color="#E9F5FF", width=1.2))
            fig.add_annotation(
                x=62, y=y+.025, showarrow=False,
                text=f"<b>{html.escape(str(train['train_id']))}</b>  {html.escape(str(train['route_group']))}",
                font=dict(size=13, color="#09111B"),
            )
            planned = int(train["planned_platform"])
            changed = " ↪" if planned != p else ""
            fig.add_annotation(
                x=62, y=y-.45, showarrow=False,
                text=f"План {planned} → Назначено {p}{changed}  ·  ожидание {float(train['waiting_min']):.1f} мин",
                font=dict(size=10, color="#C5D4E5"),
            )
            fig.add_trace(go.Scatter(
                x=[62], y=[y], mode="markers", showlegend=False,
                marker=dict(size=40, color=color, opacity=0),
                customdata=[[train["train_id"], train["route_group"], planned, p,
                             float(train["waiting_min"]), float(train["actual_departure"])]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                    "Плановая платформа: %{customdata[2]}<br>"
                    "Назначенная платформа: %{customdata[3]}<br>"
                    "Ожидание: %{customdata[4]:.2f} мин<br>"
                    "Отправление: %{customdata[5]:.2f} мин<extra></extra>"
                ),
            ))
        else:
            fig.add_annotation(x=62, y=y-.40, showarrow=False,
                               text="СВОБОДНО", font=dict(size=11, color="#627992"))
    fig.add_annotation(x=17, y=5.76, text="◀ ВХОД В ЗОНУ ПЛАТФОРМ", xanchor="left",
                       showarrow=False, font=dict(size=10, color="#8EAAC8"))
    fig.add_annotation(x=97, y=5.76, text="ВЫХОД ИЗ ЗОНЫ ▶", xanchor="right",
                       showarrow=False, font=dict(size=10, color="#8EAAC8"))
    fig.update_layout(
        title=dict(text=f"{policy.replace('_', ' ')}   ·   t = {t:.1f} мин", font=dict(color=WHITE, size=17)),
        margin=dict(l=12, r=12, t=52, b=8), height=455,
        paper_bgcolor=BG, plot_bgcolor=PANEL_BG,
        font=dict(family="Arial, sans-serif", color=WHITE),
        xaxis=dict(range=[0, 100], visible=False, fixedrange=True),
        yaxis=dict(range=[.55, 5.95], visible=False, fixedrange=True),
        hovermode="closest", showlegend=False,
    )
    return fig


def gantt_figure(df: pd.DataFrame, t: float, policy: str) -> go.Figure:
    fig = go.Figure()
    for route, group in df.groupby("route_group", sort=True):
        fig.add_trace(go.Bar(
            name=route, orientation="h",
            y=[f"Gleis {int(p)}" for p in group["assigned_platform"]],
            x=(group["actual_departure"] - group["platform_arrival"]).tolist(),
            base=group["platform_arrival"].tolist(),
            marker=dict(color=ROUTE_COLORS.get(route, "#6CD2E6"),
                        line=dict(color="#162236", width=.3)),
            customdata=np.stack([
                group["train_id"].to_numpy(),
                group["planned_platform"].to_numpy(),
                group["assigned_platform"].to_numpy(),
                np.round(group["waiting_min"].to_numpy(), 2),
                np.round(group["station_delay_min"].to_numpy(), 2),
                np.round(group["platform_arrival"].to_numpy(), 2),
                np.round(group["actual_departure"].to_numpy(), 2),
            ], axis=-1),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>План: Gleis %{customdata[1]}<br>"
                "Назначено: Gleis %{customdata[2]}<br>"
                "Ожидание: %{customdata[3]} мин<br>"
                "Вторичная задержка: %{customdata[4]} мин<br>"
                "Стоянка: %{customdata[5]}–%{customdata[6]} мин<extra></extra>"
            ),
        ))
    fig.add_vline(x=t, line=dict(color="#FDF6DF", width=2, dash="dash"))
    fig.update_layout(
        title=f"Занятость платформ — {policy.replace('_', ' ')}",
        margin=dict(l=12, r=12, t=54, b=10), height=430,
        paper_bgcolor=BG, plot_bgcolor=PANEL_BG,
        font=dict(color=WHITE),
        xaxis=dict(title="Время симуляции, мин", gridcolor="#26374B", zeroline=False),
        yaxis=dict(categoryorder="array", categoryarray=[f"Gleis {p}" for p in reversed(PLATFORMS)],
                   gridcolor="#26374B"),
        barmode="overlay", bargap=.22,
        legend=dict(orientation="h", y=-.24, x=0, font=dict(size=10)),
        hoverlabel=dict(bgcolor="#1D2E43", font_color=WHITE),
    )
    return fig


def queue_chart(fixed: pd.DataFrame, greedy: pd.DataFrame, t: float) -> go.Figure:
    horizon = max(float(fixed["actual_departure"].max()), float(greedy["actual_departure"].max()))
    grid = np.linspace(0, math.ceil(horizon), max(300, int(horizon * 3)))
    q_a, _ = timeline_counts(fixed, grid)
    q_b, _ = timeline_counts(greedy, grid)
    fig = go.Figure()
    for name, vals, color in [
        ("FIXED DB", q_a, COLOR_FIXED), ("GREEDY", q_b, COLOR_GREEDY),
    ]:
        fig.add_trace(go.Scatter(x=grid, y=vals, mode="lines", name=name,
                                 line=dict(color=color, width=2.4, shape="hv"),
                                 hovertemplate=f"{name}: %{{y}} поездов<br>t=%{{x:.1f}} мин<extra></extra>"))
    fig.add_vline(x=t, line=dict(color="#FDF6DF", dash="dash", width=2))
    fig.update_layout(
        height=340, title="Поезда в очереди во времени (оба подхода вместе)",
        xaxis=dict(title="Время симуляции, мин", gridcolor="#26374B"),
        yaxis=dict(title="Число поездов", rangemode="tozero", gridcolor="#26374B"),
        paper_bgcolor=BG, plot_bgcolor=PANEL_BG, font=dict(color=WHITE),
        margin=dict(l=12, r=12, t=55, b=10),
        legend=dict(orientation="h", y=-.28, x=0),
    )
    return fig


def train_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = {
        "train_id": "Поезд", "route_group": "Маршрут",
        "scheduled_arrival": "План. прибытие", "ready_time": "Готов к входу",
        "planned_platform": "План. Gleis", "assigned_platform": "Факт. Gleis",
        "platform_arrival": "Начало стоянки", "actual_departure": "Отправление",
        "waiting_min": "Ожидание, мин", "station_delay_min": "Вторичная задержка, мин",
    }
    frame = df[list(cols)].copy().rename(columns=cols)
    floats = frame.select_dtypes(include=["float", "float64"]).columns
    frame[floats] = frame[floats].round(2)
    return frame


def queue_table(table: pd.DataFrame) -> pd.DataFrame:
    if table.empty:
        return pd.DataFrame(columns=["Поезд", "План", "Ожидание, мин"])
    out = table[["train_id", "planned_platform", "waiting_now"]].copy()
    out.columns = ["Поезд", "План", "Ожидание, мин"]
    out["Ожидание, мин"] = out["Ожидание, мин"].round(1)
    return out.reset_index(drop=True)


def panel(df: pd.DataFrame, t: float, policy: str):
    state = classify(df, t)
    now = metrics_now(df, state)
    cols = st.columns(4)
    cols[0].metric("В очереди", now["queue"])
    cols[1].metric("На платформах", now["on_platform"])
    cols[2].metric("Отправились", f"{now['departed']} / {len(df)}")
    cols[3].metric("Задержка к t", f"{fmt(now['delay_so_far'])} мин")
    st.plotly_chart(tracks_figure(df, state, t, policy), use_container_width=True,
                    config={"displaylogo": False, "scrollZoom": False})
    north, south = st.columns(2)
    waiting = state["queued"]
    with north:
        st.markdown(f"**Очередь с севера · {sum(waiting['train_id'].str.startswith('N'))}**")
        st.dataframe(queue_table(waiting[waiting["train_id"].str.startswith("N")]),
                     hide_index=True, use_container_width=True, height=145)
    with south:
        st.markdown(f"**Очередь с юга · {sum(waiting['train_id'].str.startswith('S'))}**")
        st.dataframe(queue_table(waiting[waiting["train_id"].str.startswith("S")]),
                     hide_index=True, use_container_width=True, height=145)
    st.caption(f"На подходах (ещё не в очереди): {now['approaching']} · переназначений к t: {now['reassign_so_far']}")
    return state


def render_comparison(fixed: pd.DataFrame, greedy: pd.DataFrame):
    fa, gr = final_metrics(fixed), final_metrics(greedy)
    saving = fa["total_delay"] - gr["total_delay"]
    reduction = 100.0 * saving / fa["total_delay"] if fa["total_delay"] else 0.0
    st.markdown("### Результаты завершённого сценария")
    c = st.columns(5)
    c[0].metric("Fixed DB", f"{fmt(fa['total_delay'])} мин")
    c[1].metric("Greedy", f"{fmt(gr['total_delay'])} мин")
    c[2].metric("Снижение", f"{reduction:.1f} %")
    c[3].metric("Экономия", f"{fmt(saving)} мин")
    c[4].metric("Переназначений", gr["reassigned"])
    st.caption("Эти показатели рассчитаны по завершённому сценарию, а не только до выбранного времени t.")


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "Ingo" / "results"

st.markdown("""
<div class="hero">
  <div class="kicker">Simulation • Dispatch Replay</div>
  <div class="headline">INGOLSTADT HBF <span style="color:#46D5B2">/ PLATFORM CONTROL</span></div>
  <div class="subline">Показательная визуализация распределения Gleis 2–5 по сохранённым результатам AnyLogic</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## Настройки просмотра")
    results_str = st.text_input("Папка с CSV AnyLogic", value=str(DEFAULT_RESULTS))
    st.caption("По умолчанию: Ingo/results в корне твоего репозитория")

results_dir = Path(results_str).expanduser()
if not results_dir.is_dir():
    st.error(f"Папка не найдена: {results_dir}")
    st.info("Распакуй файлы dashboard в корень IngoHbfSimulation и проверь путь Ingo/results.")
    st.stop()

pairs = discover_pairs(results_dir)
if not pairs:
    st.error("Не найдены парные файлы train_results_FIXED_DB_Sxxx_seedxxx.csv и train_results_GREEDY_Sxxx_seedxxx.csv")
    st.stop()

with st.sidebar:
    choices = list(pairs)
    selected_key = st.selectbox("Сценарий", choices,
                                index=0,
                                format_func=lambda x: f"{x[0]} · seed {x[1]}")
    mode = st.radio("Отображение", ["Обе стратегии", "FIXED_DB", "GREEDY"],
                    index=0)
    step_size = st.select_slider("Шаг воспроизведения", options=[0.5, 1.0, 2.0, 5.0], value=1.0,
                                 format_func=lambda x: f"{x:g} мин/кадр")
    st.caption(f"Найдено {len(pairs)} парных сценариев")
    if st.button("Обновить CSV", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

scenario_id, seed = selected_key
key_name = f"{scenario_id}/{seed}"
if st.session_state.get("current_scenario") != key_name:
    st.session_state["current_scenario"] = key_name
    st.session_state["playhead"] = 0.0
    st.session_state["playing"] = False

file_stamps = tuple(
    (p.name, p.stat().st_mtime_ns)
    for p in (pairs[selected_key]["FIXED_DB"], pairs[selected_key]["GREEDY"])
)

@st.cache_data(show_spinner=False)
def cached_pair(path_string: str, sid: str, run_seed: int, stamps):
    return load_pair(Path(path_string), sid, run_seed)

try:
    fixed, greedy = cached_pair(str(results_dir), scenario_id, seed, file_stamps)
except Exception as exc:
    st.error(f"Проверка входных CSV завершилась ошибкой: {exc}")
    st.stop()

horizon = float(max(fixed["actual_departure"].max(), greedy["actual_departure"].max()))
max_time = math.ceil(horizon * 2) / 2
if float(st.session_state.get("playhead", 0.0)) > max_time:
    st.session_state["playhead"] = max_time

st.caption(f"{scenario_id} · seed {seed} · {len(fixed)} поездов · записи PML → CSV → Python · единица времени: минута")

@st.fragment(run_every="0.9s" if st.session_state.get("playing", False) else None)
def replay():
    if st.session_state.get("playing", False):
        next_t = min(max_time, float(st.session_state["playhead"]) + step_size)
        st.session_state["playhead"] = next_t
        if next_t >= max_time:
            st.session_state["playing"] = False

    c1, c2, c3, c4 = st.columns([1, 1, 1, 5])
    with c1:
        if st.button("▶ / ⏸", use_container_width=True, help="Пуск / пауза"):
            st.session_state["playing"] = not st.session_state.get("playing", False)
            st.rerun()
    with c2:
        if st.button("− 1 мин", use_container_width=True):
            st.session_state["playing"] = False
            st.session_state["playhead"] = max(0.0, float(st.session_state["playhead"]) - 1.0)
            st.rerun()
    with c3:
        if st.button("+ 1 мин", use_container_width=True):
            st.session_state["playing"] = False
            st.session_state["playhead"] = min(max_time, float(st.session_state["playhead"]) + 1.0)
            st.rerun()
    with c4:
        t = st.slider("Время симуляции", min_value=0.0, max_value=float(max_time),
                      step=0.5, key="playhead", format="%.1f мин")

    if mode == "Обе стратегии":
        left, right = st.columns(2, gap="medium")
        with left:
            st.markdown("#### 🟠 FIXED DB")
            panel(fixed, t, "FIXED_DB")
        with right:
            st.markdown("#### 🟢 GREEDY")
            panel(greedy, t, "GREEDY")
    elif mode == "FIXED_DB":
        panel(fixed, t, "FIXED_DB")
    else:
        panel(greedy, t, "GREEDY")

    st.divider()
    render_comparison(fixed, greedy)
    tab1, tab2, tab3 = st.tabs(["Занятость платформ (Gantt)", "Очереди во времени", "Таблица поездов"])
    with tab1:
        if mode == "Обе стратегии":
            a, b = st.columns(2)
            with a:
                st.plotly_chart(gantt_figure(fixed, t, "FIXED_DB"), use_container_width=True,
                                config={"displaylogo": False})
            with b:
                st.plotly_chart(gantt_figure(greedy, t, "GREEDY"), use_container_width=True,
                                config={"displaylogo": False})
        else:
            current = fixed if mode == "FIXED_DB" else greedy
            st.plotly_chart(gantt_figure(current, t, mode), use_container_width=True,
                            config={"displaylogo": False})
    with tab2:
        st.plotly_chart(queue_chart(fixed, greedy, t), use_container_width=True,
                        config={"displaylogo": False})
        st.caption("Размер очереди восстановлен по интервалам ready_time → platform_arrival.")
    with tab3:
        chosen = st.radio("Стратегия для таблицы", ["FIXED_DB", "GREEDY"], horizontal=True,
                          index=1, key="table_policy")
        current = fixed if chosen == "FIXED_DB" else greedy
        st.dataframe(train_table(current), hide_index=True, use_container_width=True, height=410)
        st.download_button(
            "Скачать данные таблицы CSV",
            current.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"dashboard_{chosen}_{scenario_id}_seed{seed}.csv",
            mime="text/csv", use_container_width=True, key="csv_download",
        )

replay()

st.info(
    "Это воспроизведение результатов завершённой симуляции, не потоковый мониторинг AnyLogic. "
    "Схема платформ условная: не является точным планом путевого развития Ingolstadt Hbf. "
    "Все показатели относятся к синтетическим сценариям."
)
