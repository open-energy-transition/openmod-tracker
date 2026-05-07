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
        pypi_package_url, date, downloads.
    """
    raw = pd.read_csv(filepath)

    # Identify date columns (format YYYY-MM)
    date_cols = [c for c in raw.columns if re.match(r"^\d{4}-\d{2}$", c)]

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
    # Skip the most recent (potentially partial) month — use the last *full* month
    last_full = months[-2] if len(months) >= 2 else months[-1]
    prev_full = months[-3] if len(months) >= 3 else None

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


def plot_download_trends(df: pd.DataFrame, selected_tool: str) -> None:
    """Line chart of monthly download trends for a single selected tool, preceded by three month-over-month metric widgets.

    Parameters
    ------------
        df: DataFrame
            Long-format downloads DataFrame. s
       selected_tool: str
            display_name of the tool to plot.
    """
    st.subheader("📈 Download Trends Over Time")

    if not selected_tool:
        st.info("Select a tool in the sidebar to see its download trend.")
        return

    tool_df = df[df["display_name"] == selected_tool].sort_values("date")

    # ── Last-3-full-months metrics ────────────────────────────────────────────
    # All months sorted; skip the latest (may be partial) → last 3 full months
    all_months = sorted(df["date"].unique())
    full_months = all_months[:-1]  # drop current partial month

    if len(full_months) >= 3:
        recent = full_months[-3:]  # [month-3, month-2, month-1]
        m_cols = st.columns(3)
        for col, month in zip(m_cols, recent):
            label = month.strftime("%B %Y")
            row = tool_df[tool_df["date"] == month]
            value = int(row["downloads"].sum()) if not row.empty else None

            # Delta vs the month before this one
            prev_idx = full_months.index(month) - 1
            if prev_idx >= 0:
                prev_row = tool_df[tool_df["date"] == full_months[prev_idx]]
                prev_value = (
                    int(prev_row["downloads"].sum()) if not prev_row.empty else None
                )
                prev_label_str = full_months[prev_idx].strftime("%B %Y")
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

    st.markdown("")  # spacing

    # ── Chart with light background ───────────────────────────────────────────
    trend_df = tool_df.copy()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=trend_df["date"],
            y=trend_df["downloads"],
            mode="lines+markers",
            name=selected_tool,
            line=dict(color="#4361EE", width=2.5),
            marker=dict(size=7, symbol="circle", color="#4361EE"),
            fill="tozeroy",
            fillcolor="rgba(67, 97, 238, 0.10)",
            hovertemplate=f"<b>{selected_tool}</b><br>%{{x|%b %Y}}: %{{y:,}}<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(text=selected_tool, font=dict(size=16), x=0.01, xanchor="left"),
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
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def show_all_packages_list(df: pd.DataFrame) -> None:
    """Scrollable list of all packages with 6-month download totals and trend.

    Parameters
    ------------
        df: DataFrame
            Long-format downloads DataFrame.
    """
    st.subheader("📋 All Packages")

    all_months = sorted(df["date"].unique())
    full_months = all_months[:-1]  # drop current partial month

    last_6 = full_months[-6:] if len(full_months) >= 6 else full_months
    prev_6 = (
        full_months[-12:-6]
        if len(full_months) >= 12
        else (full_months[: max(0, len(full_months) - 6)])
    )

    # Per-tool aggregation
    url_map = df.groupby("display_name")["html_url"].first()
    pypi_url_map = df.groupby("display_name")["pypi_package_url"].first()

    last_6_totals = (
        df[df["date"].isin(last_6)]
        .groupby("display_name")["downloads"]
        .sum()
        .rename("last_6_total")
    )
    prev_6_totals = (
        df[df["date"].isin(prev_6)]
        .groupby("display_name")["downloads"]
        .sum()
        .rename("prev_6_total")
        if prev_6
        else pd.Series(dtype=int, name="prev_6_total")
    )

    summary = (
        pd.concat([last_6_totals, prev_6_totals, url_map, pypi_url_map], axis=1)
        .reset_index()
        .sort_values("last_6_total", ascending=False)
        .reset_index(drop=True)
    )

    last_6_label = f"{last_6[0].strftime('%b %Y')} – {last_6[-1].strftime('%b %Y')}"
    prev_6_label = (
        f"{prev_6[0].strftime('%b %Y')} – {prev_6[-1].strftime('%b %Y')}"
        if prev_6
        else None
    )

    st.caption(
        f"Showing {len(summary)} packages with PyPI data · "
        f"Latest period: **{last_6_label}**"
        + (f" · Compared to: {prev_6_label}" if prev_6_label else "")
    )

    container = st.container(height=620, border=True)
    with container:
        for _, row in summary.iterrows():
            col_info, col_metric = st.columns([2, 1], vertical_alignment="center")

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
                        f'<a href="{pypi_url}" target="_blank" style="text-decoration:none; color:inherit;">'
                        f'<img src="https://pypi.org/static/images/logo-small.8998e9d1.svg" width="13" '
                        f'style="vertical-align:middle; margin-right:4px;">'
                        f"PyPI</a>"
                    )

                if links_html:
                    st.markdown(links_html, unsafe_allow_html=True)

            with col_metric:
                last_total = (
                    int(row["last_6_total"]) if pd.notna(row["last_6_total"]) else 0
                )
                prev_total = (
                    int(row["prev_6_total"])
                    if "prev_6_total" in row.index and pd.notna(row["prev_6_total"])
                    else None
                )
                delta = (
                    f"{last_total - prev_total:+,}" if prev_total is not None else None
                )
                st.metric(
                    label="Downloads (6 mo.)",
                    value=f"{last_total:,}",
                    delta=delta,
                    help=f"Δ vs previous period ({prev_6_label})"
                    if prev_6_label
                    else None,
                )

            st.divider()


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
    all_tools = sorted(df["display_name"].unique())

    # Default: top tool in latest month
    top1_default = (
        df[df["date"] == latest_month]
        .groupby("display_name")["downloads"]
        .sum()
        .idxmax()
    )

    selected_tool = st.sidebar.selectbox(
        "Select tool for trend chart",
        options=all_tools,
        index=all_tools.index(top1_default) if top1_default in all_tools else 0,
        help="Choose a tool to display in the Download Trends chart.",
    )

    # ── Metric widgets ───────────────────────────────────────────────────────
    st.markdown("---")
    show_metrics(metrics)
    st.markdown("---")

    # ── Download trend line ──────────────────────────────────────────────────
    plot_download_trends(df, selected_tool)

    st.markdown("---")

    # ── Scrollable package list ──────────────────────────────────────────────
    show_all_packages_list(df)


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
    main(df_downloads)
