# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Create Streamlit web app sub-page to visualise package download trends."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

TOP_N_DEFAULT = 20



PLOT_BG = "rgba(8, 8, 24, 0.85)"
PAPER_BG = "rgba(0, 0, 0, 0)"
GRID_COLOR = "rgba(255, 255, 255, 0.06)"
FONT_COLOR = "#e2e8f0"
PLOT_TEMPLATE = "plotly_dark"


@st.cache_data
def load_downloads(filepath: Path) -> pd.DataFrame:
    """Load and reshape the package downloads CSV into long format.

    Args:
        filepath: Path to package_downloads.csv.

    Returns:
        Long-format DataFrame with columns: id, display_name, html_url,
        pypi_package_url, date, downloads.
    """
    raw = pd.read_csv(filepath)

    # Identify date columns (format YYYY-MM)
    date_cols = [c for c in raw.columns if len(c) == 7 and c[4] == "-" and c[:4].isdigit()]

    # Prefer pypi_package_name as display name, fall back to id
    raw["display_name"] = raw["pypi_package_name"].fillna(raw["id"])

    # Melt to long format and drop rows with no download count
    long = raw.melt(
        id_vars=["id", "display_name", "html_url", "pypi_package_url"],
        value_vars=date_cols,
        var_name="date",
        value_name="downloads",
    )
    long["date"] = pd.to_datetime(long["date"])
    long = long.dropna(subset=["downloads"]).copy()
    long["downloads"] = long["downloads"].astype(int)
    return long


def compute_metrics(df: pd.DataFrame) -> dict:
    """Compute summary statistics for the metric widgets.

    Args:
        df: Long-format downloads DataFrame.

    Returns:
        Dict with latest_month, prev_month, totals, top tool name/count,
        all_time_total, and tool count.
    """
    months = sorted(df["date"].unique())
    latest, prev = months[-1], months[-2] if len(months) >= 2 else None

    month_totals = df.groupby("date")["downloads"].sum()
    latest_total = int(month_totals[latest])
    prev_total = int(month_totals[prev]) if prev is not None else None

    top_series = df[df["date"] == latest].groupby("display_name")["downloads"].sum()
    top_tool = str(top_series.idxmax())
    top_tool_dl = int(top_series.max())

    return {
        "latest_month": latest,
        "prev_month": prev,
        "latest_total": latest_total,
        "prev_total": prev_total,
        "top_tool": top_tool,
        "top_tool_downloads": top_tool_dl,
        "all_time_total": int(df["downloads"].sum()),
        "tools_count": int(df["display_name"].nunique()),
    }


def show_metrics(metrics: dict) -> None:
    """Render st.metric widgets in a four-column row.

    Args:
        metrics: Dict produced by compute_metrics().
    """
    latest_label = metrics["latest_month"].strftime("%b %Y")
    prev_label = metrics["prev_month"].strftime("%b %Y") if metrics["prev_month"] else None

    delta_str = None
    if metrics["prev_total"] is not None:
        diff = metrics["latest_total"] - metrics["prev_total"]
        delta_str = f"{diff:+,}  vs {prev_label}"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        label=f"📥 Total Downloads — {latest_label}",
        value=f"{metrics['latest_total']:,}",
        delta=delta_str,
    )
    col2.metric(
        label="🏆 Top Tool This Month",
        value=metrics["top_tool"],
        delta=f"{metrics['top_tool_downloads']:,} downloads",
        delta_color="off",
    )
    col3.metric(
        label="📦 Tools with Download Data",
        value=str(metrics["tools_count"]),
    )
    col4.metric(
        label="🌐 All-Time Tracked Downloads",
        value=f"{metrics['all_time_total']:,}",
    )


def _base_layout(height: int = 480, extra: dict = None) -> dict:
    """Return a shared Plotly layout dict with the glowy dark theme.

    Args:
        height: Chart height in pixels.
        extra: Additional layout keys to merge in.

    Returns:
        Layout dict for use in go.Figure.update_layout().
    """
    layout = dict(
        template=PLOT_TEMPLATE,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        height=height,
        margin=dict(l=10, r=10, t=30, b=40),
        font=dict(color=FONT_COLOR, family="Inter, sans-serif"),
        xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
    )
    if extra:
        layout.update(extra)
    return layout


def plot_top_tools_bar(df: pd.DataFrame, latest_month: pd.Timestamp, n: int) -> None:
    """Horizontal bar chart of the top N tools by downloads in a given month.

    Args:
        df: Long-format downloads DataFrame.
        latest_month: Month to rank tools by.
        n: How many tools to show.
    """
    month_label = latest_month.strftime("%B %Y")
    st.subheader(f"🔥 Top {n} Tools — {month_label}")

    top = (
        df[df["date"] == latest_month]
        .groupby("display_name")["downloads"]
        .sum()
        .nlargest(n)
        .reset_index()
        .sort_values("downloads", ascending=True)
    )

    fig = go.Figure(
        go.Bar(
            x=top["downloads"],
            y=top["display_name"],
            orientation="h",
            text=top["downloads"].apply(lambda v: f"{v:,}"),
            textposition="outside",
            textfont=dict(color=FONT_COLOR, size=11),
            marker=dict(
                color=top["downloads"],
                colorscale="Plasma",
                showscale=False,
                line=dict(color="rgba(255,255,255,0.08)", width=0.8),
            ),
            hovertemplate="<b>%{y}</b><br>Downloads: %{x:,}<extra></extra>",
        )
    )
    fig.update_layout(
        **_base_layout(
            height=max(380, n * 24),
            extra=dict(
                xaxis=dict(
                    title="Monthly Downloads",
                    gridcolor=GRID_COLOR,
                    tickformat=",",
                ),
                yaxis=dict(title="", gridcolor=GRID_COLOR),
            ),
        )
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def plot_treemap(df: pd.DataFrame, latest_month: pd.Timestamp) -> None:
    """Treemap of download share for the latest month.

    Args:
        df: Long-format downloads DataFrame.
        latest_month: Month to visualise.
    """
    month_label = latest_month.strftime("%B %Y")
    st.subheader(f"🗺️ Download Share — {month_label}")

    share_df = (
        df[df["date"] == latest_month]
        .groupby("display_name")["downloads"]
        .sum()
        .reset_index()
    )

    fig = px.treemap(
        share_df,
        path=["display_name"],
        values="downloads",
        color="downloads",
        color_continuous_scale="Plasma",
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{value:,}",
        hovertemplate="<b>%{label}</b><br>Downloads: %{value:,}<extra></extra>",
        marker_line_width=1,
        marker_line_color="rgba(255,255,255,0.12)",
    )
    fig.update_layout(
        template=PLOT_TEMPLATE,
        paper_bgcolor=PAPER_BG,
        height=500,
        margin=dict(l=0, r=0, t=10, b=0),
        font=dict(color=FONT_COLOR),
        coloraxis_colorbar=dict(title="Downloads", tickformat=","),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def plot_download_trends(df: pd.DataFrame, selected_tools: list[str]) -> None:
    """Multi-line chart of monthly download trends for selected tools.

    Args:
        df: Long-format downloads DataFrame.
        selected_tools: List of display_name values to plot.
    """
    st.subheader("📈 Download Trends Over Time")

    if not selected_tools:
        st.info("Select one or more tools in the sidebar to compare their download trends.")
        return

    trend_df = df[df["display_name"].isin(selected_tools)].sort_values("date")

    # Build a colour cycle from two qualitative palettes for contrast
    palette = px.colors.qualitative.Plotly + px.colors.qualitative.Light24
    color_map = {
        tool: palette[i % len(palette)]
        for i, tool in enumerate(sorted(selected_tools))
    }

    fig = go.Figure()
    for tool in sorted(selected_tools):
        t = trend_df[trend_df["display_name"] == tool]
        fig.add_trace(
            go.Scatter(
                x=t["date"],
                y=t["downloads"],
                mode="lines+markers",
                name=tool,
                line=dict(color=color_map[tool], width=2.5),
                marker=dict(size=7, symbol="circle"),
                hovertemplate=f"<b>{tool}</b><br>%{{x|%b %Y}}: %{{y:,}}<extra></extra>",
            )
        )

    fig.update_layout(
        **_base_layout(
            height=460,
            extra=dict(
                xaxis=dict(
                    title="Month",
                    type="date",
                    gridcolor=GRID_COLOR,
                ),
                yaxis=dict(
                    title="Monthly Downloads",
                    gridcolor=GRID_COLOR,
                    tickformat=",",
                ),
                hovermode="x unified",
                legend=dict(
                    bgcolor="rgba(0,0,0,0.5)",
                    bordercolor="rgba(255,255,255,0.1)",
                    borderwidth=1,
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=0.01,
                    orientation="h",
                ),
            ),
        )
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def plot_monthly_heatmap(df: pd.DataFrame, n: int) -> None:
    """Heatmap of monthly downloads for the top N tools.

    Args:
        df: Long-format downloads DataFrame.
        n: Number of top tools (by total downloads) to include.
    """
    st.subheader("🌡️ Monthly Downloads Heatmap")

    top_tools = (
        df.groupby("display_name")["downloads"].sum().nlargest(n).index.tolist()
    )
    heat_df = df[df["display_name"].isin(top_tools)].copy()
    heat_df["month_str"] = heat_df["date"].dt.strftime("%Y-%m")

    pivot = (
        heat_df.pivot_table(
            index="display_name", columns="month_str", values="downloads", aggfunc="sum"
        )
        .fillna(0)
    )
    # Sort rows by total downloads (ascending so top tool is at top of chart)
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=True).index]

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="Plasma",
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:,.0f}<extra></extra>",
            colorbar=dict(
                title="Downloads",
                tickformat=",",
                thickness=14,
                len=0.8,
            ),
        )
    )
    fig.update_layout(
        **_base_layout(
            height=max(440, n * 22),
            extra=dict(
                xaxis=dict(
                    title="Month",
                    tickangle=-45,
                    gridcolor=GRID_COLOR,
                ),
                yaxis=dict(title="", automargin=True, gridcolor=GRID_COLOR),
            ),
        )
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def preamble() -> None:
    """Introductory text shown before the charts."""
    st.markdown(
        """
        Package downloads are a strong proxy for **real-world tool usage** as they capture users who actually install and run a tool.

       Here we track **monthly PyPI downloads** for energy modelling tools that publish
        Python packages, spanning the past year.
        """
    )
    st.info(
        """
        **Notes on the data**
        - **PyPI only.** Tools distributed exclusively via conda-forge, Julia's General
          registry, Maven Central, or other ecosystems are not reflected here.
        - **Bot & CI traffic.** Automated downloads by CI pipelines are not considered in this infographic.
        - **Partial current month.** The most recently started month may show lower counts
          simply because it is not yet complete; look to the previous full month for a
          stable baseline.
        """,
        icon="ℹ️",
    )


def main(df: pd.DataFrame) -> None:
    """Orchestrate the page layout and visualisations.

    Args:
        df: Long-format downloads DataFrame from load_downloads().
    """
    metrics = compute_metrics(df)
    latest_month = metrics["latest_month"]

    # ── Sidebar controls ─────────────────────────────────────────────────────
    top5_defaults = (
        df[df["date"] == latest_month]
        .groupby("display_name")["downloads"]
        .sum()
        .nlargest(5)
        .index.tolist()
    )
    all_tools = sorted(df["display_name"].unique())

    selected_tools = st.sidebar.multiselect(
        "Select tools for trend chart",
        options=all_tools,
        default=[t for t in top5_defaults if t in all_tools],
        help="Choose tools to compare in the Download Trends chart.",
    )
    st.sidebar.markdown("---")
    top_n = st.sidebar.slider(
        "Top N tools to display",
        min_value=5,
        max_value=30,
        value=TOP_N_DEFAULT,
        step=5,
        help="Controls how many tools appear in the bar chart and heatmap.",
    )


    # ── Metric widgets ───────────────────────────────────────────────────────
    show_metrics(metrics)
    st.markdown("---")

    # ── Bar chart + Treemap side by side ─────────────────────────────────────
    col_bar, col_tree = st.columns(2, gap="medium")
    with col_bar:
        plot_top_tools_bar(df, latest_month, n=top_n)
    with col_tree:
        plot_treemap(df, latest_month)

    st.markdown("---")

    # ── Download trend lines ─────────────────────────────────────────────────
    plot_download_trends(df, selected_tools)

    st.markdown("---")

    # ── Heatmap ──────────────────────────────────────────────────────────────
    plot_monthly_heatmap(df, n=top_n)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Package Download Trends",
        page_icon="📦",
        layout="wide",
    )

    st.title("Package Download Trends")
    st.text(
        "Explore how energy modelling tools are downloaded month by month "
        "across the open-source community."
    )

    data_path = (
        Path().cwd()
        / "user_analysis"
        / "output"
        / "package_downloads.csv"
    )

    df_downloads = load_downloads(data_path)

    preamble()
    main(df_downloads)

