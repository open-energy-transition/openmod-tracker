# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Create Streamlit web app sub-page to visualise package download trends."""

import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


@st.cache_data
def load_downloads(filepath: Path) -> pd.DataFrame:
    """Load and reshape the package downloads CSV into long format.

    Parameters
    ------------
        filepath: Path to package_downloads.csv.

    Returns:
    --------
        Long-format DataFrame with columns: id, display_name, html_url,
        pypi_package_url, anaconda_package_url, juliahub_package_url,
        other_source, date, downloads.
    """
    raw = pd.read_csv(filepath)

    # Identify date columns (format YYYY-MM)
    date_cols = [c for c in raw.columns if re.match(r"^\d{4}-\d{2}$", c)]

    # Prefer pypi_package_name as display name, fall back to id
    raw["display_name"] = raw["pypi_package_name"].fillna(raw["id"])

    # Melt to long format and drop rows with no download count
    long = raw.melt(
        id_vars=[
            "id",
            "display_name",
            "html_url",
            "pypi_package_url",
            "anaconda_package_url",
            "juliahub_package_url",
            "other_source",
        ],
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

    Parameters
    ------------
        df: DataFrame
            Long-format downloads DataFrame.

    Returns:
    --------
        Dict with latest_month, prev_month, totals, top tool name/count,
        all_time_total, and tool count.
    """
    months = sorted(df["date"].unique())
    last_full = months[-1]
    prev_full = months[-2] if len(months) >= 2 else None

    month_totals = df.groupby("date")["downloads"].sum()
    latest_total = int(month_totals[last_full])
    prev_total = int(month_totals[prev_full]) if prev_full is not None else None

    top_series = df[df["date"] == last_full].groupby("display_name")["downloads"].sum()
    top_tool = str(top_series.idxmax())
    top_tool_dl = int(top_series.max())

    return {
        "latest_month": last_full,
        "prev_month": prev_full,
        "latest_total": latest_total,
        "prev_total": prev_total,
        "top_tool": top_tool,
        "top_tool_downloads": top_tool_dl,
        "all_time_total": int(df["downloads"].sum()),
        "tools_count": int(df["display_name"].nunique()),
    }


def show_metrics(metrics: dict) -> None:
    """Render st.metric widgets in a four-column row.

    Parameters
    ------------
        metrics: Dict produced by compute_metrics().
    """
    st.subheader("💡Quick stats")

    latest_label = metrics["latest_month"].strftime("%b %Y")
    prev_label = (
        metrics["prev_month"].strftime("%b %Y") if metrics["prev_month"] else None
    )

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
    # Render top-tool with a smaller font so long names always fit
    col2.markdown(
        f"<div style='font-size:0.8rem; color:gray; margin-bottom:4px'>🏆 Top Tool — {latest_label}</div>"
        f"<div style='font-size:1rem; font-weight:700; line-height:1.3; word-break:break-word'>{metrics['top_tool']}</div>"
        f"<div style='font-size:0.85rem; color:gray; margin-top:4px'>{metrics['top_tool_downloads']:,} downloads</div>",
        unsafe_allow_html=True,
    )
    col3.metric(label="📦 Tools with Download Data", value=str(metrics["tools_count"]))
    col4.metric(
        label="🌐 All-Time Tracked Downloads", value=f"{metrics['all_time_total']:,}"
    )


def plot_download_trends(df: pd.DataFrame, selected_tools: list) -> None:
    """Line chart of monthly download trends for selected tools.

    Parameters
    ------------
        df: DataFrame
            Long-format downloads DataFrame.
       selected_tools: list
            List of display_names to plot (max 5). Empty list = all tools.
    """
    st.subheader("📈 Download Trends Over Time")

    # Colorblind-friendly palette (Okabe-Ito palette)
    colors = [
        "#0173B2",  # Blue
        "#DE8F05",  # Orange
        "#029E73",  # Green
        "#CC78BC",  # Purple
        "#CA9161",  # Brown
        "#949494",  # Grey (for average)
    ]

    if not selected_tools:
        # Show aggregated trend for all tools (normalized)
        tool_df = df.copy()
        plot_title = "All Tools (Average Downloads per Tool)"
    else:
        tool_df = df[df["display_name"].isin(selected_tools)].copy()
        if len(selected_tools) == 1:
            plot_title = selected_tools[0]
        else:
            plot_title = f"{len(selected_tools)} Selected Tools"

    # ── Last-3-full-months metrics ────────────────────────────────────────────
    all_months = sorted(df["date"].unique())

    if len(all_months) >= 3:
        recent = all_months[-3:]
        m_cols = st.columns(3)
        for col, month in zip(m_cols, recent):
            label = month.strftime("%B %Y")
            row = tool_df[tool_df["date"] == month]

            if not selected_tools:
                # Average downloads per tool
                value = (
                    int(row["downloads"].sum() / df["display_name"].nunique())
                    if not row.empty
                    else None
                )
            else:
                # Total for selected tools
                value = int(row["downloads"].sum()) if not row.empty else None

            prev_idx = all_months.index(month) - 1
            if prev_idx >= 0:
                prev_row = tool_df[tool_df["date"] == all_months[prev_idx]]
                if not selected_tools:
                    prev_value = (
                        int(prev_row["downloads"].sum() / df["display_name"].nunique())
                        if not prev_row.empty
                        else None
                    )
                else:
                    prev_value = (
                        int(prev_row["downloads"].sum()) if not prev_row.empty else None
                    )
                prev_label_str = all_months[prev_idx].strftime("%B %Y")
            else:
                prev_value = None
                prev_label_str = None

            delta = (
                f"{value - prev_value:+,}"
                if (value is not None and prev_value is not None)
                else None
            )
            help_text = (
                f"Change compared to {prev_label_str}" if prev_label_str else None
            )
            col.metric(
                label=label,
                value=f"{value:,}" if value is not None else "—",
                delta=delta,
                help=help_text,
            )

    st.markdown("")

    # ── Chart with light background ───────────────────────────────────────────
    fig = go.Figure()

    if not selected_tools:
        # Aggregate all tools - show average per tool
        agg_df = tool_df.groupby("date")["downloads"].sum().reset_index()
        agg_df["downloads"] = agg_df["downloads"] / df["display_name"].nunique()

        fig.add_trace(
            go.Scatter(
                x=agg_df["date"],
                y=agg_df["downloads"],
                mode="lines+markers",
                name="Average per Tool",
                line=dict(color=colors[0], width=2.5),
                marker=dict(size=7, symbol="circle", color=colors[0]),
                fill="tozeroy",
                fillcolor=f"rgba({int(colors[0][1:3], 16)}, {int(colors[0][3:5], 16)}, {int(colors[0][5:7], 16)}, 0.10)",
                hovertemplate="<b>Average per Tool</b><br>%{x|%b %Y}: %{y:,.0f}<extra></extra>",
            )
        )
    elif len(selected_tools) == 1:
        # Single tool - show with fill
        trend_df = tool_df[tool_df["display_name"] == selected_tools[0]].sort_values(
            "date"
        )
        fig.add_trace(
            go.Scatter(
                x=trend_df["date"],
                y=trend_df["downloads"],
                mode="lines+markers",
                name=selected_tools[0],
                line=dict(color=colors[0], width=2.5),
                marker=dict(size=7, symbol="circle", color=colors[0]),
                fill="tozeroy",
                fillcolor=f"rgba({int(colors[0][1:3], 16)}, {int(colors[0][3:5], 16)}, {int(colors[0][5:7], 16)}, 0.10)",
                hovertemplate=f"<b>{selected_tools[0]}</b><br>%{{x|%b %Y}}: %{{y:,}}<extra></extra>",
            )
        )
    else:
        # Multiple tools - show individual lines + average
        for idx, tool in enumerate(selected_tools):
            trend_df = tool_df[tool_df["display_name"] == tool].sort_values("date")
            fig.add_trace(
                go.Scatter(
                    x=trend_df["date"],
                    y=trend_df["downloads"],
                    mode="lines+markers",
                    name=tool,
                    line=dict(color=colors[idx % len(colors)], width=2),
                    marker=dict(
                        size=6, symbol="circle", color=colors[idx % len(colors)]
                    ),
                    hovertemplate=f"<b>{tool}</b><br>%{{x|%b %Y}}: %{{y:,}}<extra></extra>",
                )
            )

        # Add average line
        agg_df = tool_df.groupby("date")["downloads"].sum().reset_index()
        agg_df["downloads"] = agg_df["downloads"] / len(selected_tools)

        fig.add_trace(
            go.Scatter(
                x=agg_df["date"],
                y=agg_df["downloads"],
                mode="lines",
                name="Average",
                line=dict(color=colors[5], width=2.5, dash="dash"),
                hovertemplate="<b>Average</b><br>%{x|%b %Y}: %{y:,.0f}<extra></extra>",
            )
        )

    fig.update_layout(
        title=dict(text=plot_title, font=dict(size=16), x=0.01, xanchor="left"),
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=380,
        margin=dict(l=10, r=10, t=50, b=40),
        font=dict(family="Inter, sans-serif"),
        xaxis=dict(
            title="Month",
            type="date",
            gridcolor="rgba(0,0,0,0.07)",
            zerolinecolor="rgba(0,0,0,0.1)",
        ),
        yaxis=dict(
            title="Monthly Downloads",
            gridcolor="rgba(0,0,0,0.07)",
            zerolinecolor="rgba(0,0,0,0.1)",
            tickformat=",",
        ),
        hovermode="x unified",
        showlegend=len(selected_tools) > 1,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def show_all_packages_list(
    df: pd.DataFrame, filepath: Path, selected_tools: list, tools_with_data_count: int, delta_display_mode: str
) -> None:
    """Scrollable list of all packages with latest month downloads and year-to-year comparison.

    Parameters
    ------------
        df: DataFrame
            Long-format downloads DataFrame.
        filepath: Path
            Path to the original CSV file to load all packages.
        selected_tools: list
            List of selected tools to filter display.
        tools_with_data_count: int
            Total count of tools with download data (from compute_metrics).
        delta_display_mode: str
            "absolute" or "percentage" to control how deltas are shown in the metrics.
    """
    st.subheader("📋 All Packages")

    all_months = sorted(df["date"].unique())

    # Get latest month and previous month (for MoM)
    latest_month = all_months[-1]
    prev_month = all_months[-2] if len(all_months) >= 2 else None

    # ── YoY windows ──────────────────────────────────────────────────────────
    # Recent 12 months: latest_month-11 → latest_month  (e.g. Jun 2025 – May 2026)
    recent_window_end = pd.Timestamp(latest_month)
    recent_window_start = recent_window_end - pd.DateOffset(months=11)
    # Previous 12 months: latest_month-23 → latest_month-12 (e.g. Jun 2024 – May 2025)
    prev_window_end = recent_window_start - pd.DateOffset(months=1)
    prev_window_start = prev_window_end - pd.DateOffset(months=11)

    recent_months = [
        m
        for m in all_months
        if recent_window_start <= pd.Timestamp(m) <= recent_window_end
    ]
    prev_year_months = [
        m for m in all_months if prev_window_start <= pd.Timestamp(m) <= prev_window_end
    ]

    # Load all packages from original CSV (including those without downloads)
    all_packages = pd.read_csv(filepath)
    all_packages["display_name"] = all_packages["pypi_package_name"].fillna(
        all_packages["id"]
    )

    # Get download totals for different periods
    latest_totals = (
        df[df["date"] == latest_month]
        .groupby("display_name")["downloads"]
        .sum()
        .rename("latest_total")
    )

    prev_totals = (
        df[df["date"] == prev_month]
        .groupby("display_name")["downloads"]
        .sum()
        .rename("prev_total")
        if prev_month is not None
        else pd.Series(dtype=int, name="prev_total")
    )

    # Sum downloads over the two 12-month windows per package
    recent_year_totals = (
        df[df["date"].isin(recent_months)]
        .groupby("display_name")["downloads"]
        .sum()
        .rename("recent_year_total")
        if recent_months
        else pd.Series(dtype=int, name="recent_year_total")
    )

    prev_year_totals = (
        df[df["date"].isin(prev_year_months)]
        .groupby("display_name")["downloads"]
        .sum()
        .rename("prev_year_total")
        if prev_year_months
        else pd.Series(dtype=int, name="prev_year_total")
    )

    # Create summary from all packages
    summary = all_packages[
        [
            "display_name",
            "html_url",
            "pypi_package_url",
            "anaconda_package_url",
            "juliahub_package_url",
            "other_source",
        ]
    ].copy()

    # Join with download data
    summary = summary.merge(
        latest_totals, left_on="display_name", right_index=True, how="left"
    )
    if not prev_totals.empty:
        summary = summary.merge(
            prev_totals, left_on="display_name", right_index=True, how="left"
        )
    if not recent_year_totals.empty:
        summary = summary.merge(
            recent_year_totals, left_on="display_name", right_index=True, how="left"
        )
    if not prev_year_totals.empty:
        summary = summary.merge(
            prev_year_totals, left_on="display_name", right_index=True, how="left"
        )

    # Filter by selected tools if applicable
    if selected_tools:
        summary = summary[summary["display_name"].isin(selected_tools)].copy()

    # Sort: packages with data first (by download count), then packages without data (alphabetically)
    summary["has_data"] = summary["latest_total"].notna()
    summary = summary.sort_values(
        ["has_data", "latest_total", "display_name"],
        ascending=[False, False, True],
        na_position="last",
    ).reset_index(drop=True)

    latest_label = latest_month.strftime("%b %Y")
    prev_label = prev_month.strftime("%b %Y") if prev_month is not None else None
    recent_window_label = (
        f"{recent_window_start.strftime('%b %Y')} – {recent_window_end.strftime('%b %Y')}"
        if recent_months
        else None
    )
    prev_window_label = (
        f"{prev_window_start.strftime('%b %Y')} – {prev_window_end.strftime('%b %Y')}"
        if prev_year_months
        else None
    )

    filter_text = (
        f" (filtered to {len(selected_tools)} selected)" if selected_tools else ""
    )
    caption_text = (
        f"Showing {len(summary)} packages{filter_text} ({tools_with_data_count} with download data) · "
        f"Latest month: **{latest_label}**"
    )
    if prev_label:
        caption_text += f" · MoM comparison: {prev_label}"
    if recent_window_label and prev_window_label:
        caption_text += f" · YoY: {recent_window_label} vs {prev_window_label}"

    st.caption(caption_text)

    container = st.container(height=620, border=True)
    with container:
        for _, row in summary.iterrows():
            col_info, col_metric1, col_metric2 = st.columns(
                [2, 1, 1], vertical_alignment="center"
            )

            with col_info:
                st.markdown(f"**{row['display_name']}**")
                links_html = ""

                url = row.get("html_url")
                if pd.notna(url):
                    url = str(url)
                    if "github.com" in url:
                        icon = "https://github.com/favicon.ico"
                        host = "GitHub"
                    elif "gitlab" in url:
                        icon = "https://gitlab.com/assets/favicon-72a2cad5025aa931d6ea56c3201d1f18e68a8cd39788c7c80d5b2b82aa5143ef.png"
                        host = "GitLab"
                    else:
                        icon, host = None, "Repository"

                    links_html += (
                        f'<a href="{url}" target="_blank" style="text-decoration:none; color:inherit; margin-right:12px;">'
                        + (
                            f'<img src="{icon}" width="13" style="vertical-align:middle; margin-right:4px; border-radius:2px">'
                            if icon
                            else ""
                        )
                        + f"{host}</a>"
                    )

                pypi_url = row.get("pypi_package_url")
                if pd.notna(pypi_url):
                    links_html += (
                        f'<a href="{pypi_url}" target="_blank" style="text-decoration:none; color:inherit; margin-right:12px;">'
                        f'<img src="https://pypi.org/static/images/logo-small.8998e9d1.svg" width="13" '
                        f'style="vertical-align:middle; margin-right:4px;">'
                        f"PyPI</a>"
                    )

                anaconda_url = row.get("anaconda_package_url")
                if pd.notna(anaconda_url):
                    links_html += (
                        f'<a href="{anaconda_url}" target="_blank" style="text-decoration:none; color:inherit; margin-right:12px;">'
                        f'<img src="https://www.anaconda.com/favicon.ico" width="13" '
                        f'style="vertical-align:middle; margin-right:4px;">'
                        f"Anaconda</a>"
                    )

                juliahub_url = row.get("juliahub_package_url")
                if pd.notna(juliahub_url):
                    links_html += (
                        f'<a href="{juliahub_url}" target="_blank" style="text-decoration:none; color:inherit; margin-right:12px;">'
                        f'<img src="https://juliahub.com/favicon.ico" width="13" '
                        f'style="vertical-align:middle; margin-right:4px;">'
                        f"JuliaHub</a>"
                    )

                other_source = row.get("other_source")
                if pd.notna(other_source):
                    other_source_str = str(other_source)
                    if "central.sonatype.com" in other_source_str:
                        links_html += (
                            f'<a href="{other_source_str}" target="_blank" style="text-decoration:none; color:inherit; margin-right:12px;">'
                            f'<img src="https://central.sonatype.com/favicon.ico" width="13" '
                            f'style="vertical-align:middle; margin-right:4px;">'
                            f"Maven</a>"
                        )
                    elif "crates.io" in other_source_str:
                        links_html += (
                            f'<a href="{other_source_str}" target="_blank" style="text-decoration:none; color:inherit; margin-right:12px;">'
                            f'<img src="https://crates.io/favicon.ico" width="13" '
                            f'style="vertical-align:middle; margin-right:4px;">'
                            f"Cargo</a>"
                        )

                if links_html:
                    st.markdown(links_html, unsafe_allow_html=True)

            # Check if package has download data
            if row.get("has_data", False):
                latest_total = (
                    int(row["latest_total"]) if pd.notna(row["latest_total"]) else 0
                )

                # Month-over-month comparison
                with col_metric1:
                    prev_total = (
                        int(row["prev_total"])
                        if "prev_total" in row.index and pd.notna(row["prev_total"])
                        else None
                    )
                    if prev_total is not None:
                        diff_mom = latest_total - prev_total
                        if delta_display_mode == "Percentage":
                            if prev_total > 0:
                                delta_mom = f"{(diff_mom / prev_total) * 100:+.1f}%"
                            else:
                                delta_mom = None
                        else:
                            delta_mom = f"{diff_mom:+,}"
                    else:
                        delta_mom = None
                    st.metric(
                        label=f"{latest_label}",
                        value=f"{latest_total:,}",
                        delta=delta_mom,
                        help=f"MoM: Δ vs {prev_label}" if prev_label else None,
                    )

                # Year-over-year comparison (12-month window vs previous 12-month window)
                with col_metric2:
                    recent_year_total = (
                        int(row["recent_year_total"])
                        if "recent_year_total" in row.index
                        and pd.notna(row["recent_year_total"])
                        else None
                    )
                    prev_year_total = (
                        int(row["prev_year_total"])
                        if "prev_year_total" in row.index
                        and pd.notna(row["prev_year_total"])
                        else None
                    )
                    if recent_year_total is not None and prev_year_total is not None:
                        delta_yoy = f"{recent_year_total - prev_year_total:+,}"
                        st.metric(
                            label="Last year",
                            value=recent_year_total,
                            delta=delta_yoy,
                            help=(
                                f"YoY: {recent_window_label} vs {prev_window_label}"
                                if recent_window_label and prev_window_label
                                else None
                            ),
                        )
                    else:
                        st.markdown(
                            '<div style="background: #f8f8f8; color: #999; padding: 8px; border-radius: 4px; text-align: center; font-size: 0.75rem;">'
                            "No YoY data"
                            "</div>",
                            unsafe_allow_html=True,
                        )
            else:
                # Show grey indicator for packages without download data
                with col_metric1:
                    st.markdown(
                        '<div style="background: #f0f0f0; color: #888; padding: 8px; border-radius: 4px; text-align: center; font-size: 0.85rem;">'
                        "⊘ No data"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                with col_metric2:
                    st.markdown(
                        '<div style="background: #f0f0f0; color: #888; padding: 8px; border-radius: 4px; text-align: center; font-size: 0.85rem;">'
                        "⊘ No data"
                        "</div>",
                        unsafe_allow_html=True,
                    )

            st.divider()


def preamble() -> None:
    """Introductory text shown before the charts."""
    st.markdown(
        """
        Package downloads are a strong proxy for **real-world tool usage** as they capture users who actually install and run a tool.

       Here we track **monthly PyPI and Conda downloads** for energy modelling tools that publish
        Python packages, spanning the past year.
        """
    )
    st.info(
        """
        **Notes on the data**
        - **PyPI and Conda only.** Tools distributed exclusively via Julia's General
          registry, Maven Central, or other ecosystems are not reflected here.
        - **Bot & CI traffic.** Automated downloads by CI pipelines are not considered in this infographic.
        - **No current month.** The current month is not shown as the complete data is not yet available.
        """,
        icon="ℹ️",
    )


def main(df: pd.DataFrame, filepath: Path) -> None:
    """Orchestrate the page layout and visualisations.

    Args:
        df: Long-format downloads DataFrame from load_downloads().
        filepath: Path to the original CSV file.
    """
    metrics = compute_metrics(df)

    # ── Sidebar controls ─────────────────────────────────────────────────────
    all_tools = sorted(df["display_name"].unique())

    delta_display_mode = st.sidebar.radio(
        "Delta display",
        options=["Absolute", "Percentage"],
        index=0,
        help="Choose whether MoM/YoY deltas are shown as absolute numbers or percentages.",
    )

    selected_tools = st.sidebar.multiselect(
        "Select tools for trend chart (max 5)",
        options=all_tools,
        default=[],
        max_selections=5,
        help="Choose up to 5 tools. Leave empty to see the average across all tools.",
    )

    # ── Metric widgets ───────────────────────────────────────────────────────
    st.markdown("---")
    show_metrics(metrics)
    st.markdown("---")

    # ── Download trend line ──────────────────────────────────────────────────
    plot_download_trends(df, selected_tools)

    st.markdown("---")

    # ── Scrollable package list ──────────────────────────────────────────────
    show_all_packages_list(df, filepath, selected_tools, metrics["tools_count"], delta_display_mode)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Package Download Trends", page_icon="📦", layout="wide"
    )

    st.title("Package Download Trends")
    st.text(
        "Explore how energy modelling tools are downloaded month by month "
        "across the open-source community."
    )

    data_path = Path().cwd() / "user_analysis" / "output" / "package_downloads.csv"

    df_downloads = load_downloads(data_path)

    preamble()
    main(df_downloads, data_path)
