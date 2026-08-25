# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Unified deep dive page combining all tool analyses."""

import textwrap
from pathlib import Path

import jinja2
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
import util

# Configuration
FIG_CONFIG = {"displayModeBar": False, "doubleClick": False, "scrollZoom": False}
RESOLUTION_CONVERTER = {"Daily": "D", "Weekly": "W", "Monthly": "ME"}
KEEP_TOP = 15

# Paths
path_cwd = Path.cwd()
user_stats_dir = path_cwd / "user_analysis" / "output"
scores_path = path_cwd / "inventory" / "output" / "scores.csv"
reasons_path = path_cwd / "inventory" / "output" / "reasons.csv"
downloads_path = path_cwd / "user_analysis" / "output" / "package_downloads.csv"

# Jinja2 for OSSF
_templates_dir = path_cwd / "website" / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_templates_dir)),
    autoescape=jinja2.select_autoescape(["html"]),
)


# ============================================================================
# Data Loading Functions
# ============================================================================


@st.cache_data
def load_user_classifications() -> pd.DataFrame:
    """Load user classification data."""
    return pd.read_csv(user_stats_dir / "user_classifications.csv")


@st.cache_data
def load_repo_interactions() -> pd.DataFrame:
    """Load repository interactions data."""
    df = pd.read_csv(
        user_stats_dir / "repo_interactions.csv",
        parse_dates=["created", "closed", "merged"],
    ).dropna(subset=["username", "repo"], how="any")
    return df.drop_duplicates()


@st.cache_data
def load_ossf_scores() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load OSSF Scorecard data."""
    scores = pd.read_csv(scores_path, index_col="id")
    reasons = pd.read_csv(reasons_path, index_col="id")
    return scores, reasons


@st.cache_data
def load_downloads() -> pd.DataFrame:
    """Load package downloads data."""
    import re

    raw = pd.read_csv(downloads_path)
    date_cols = [c for c in raw.columns if re.match(r"^\d{4}-\d{2}$", c)]
    raw["display_name"] = raw["pypi_package_name"].fillna(raw["id"])
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


@st.cache_data
def map_repo_to_tool(repos: list[str]) -> dict:
    """Map repository URLs to tool names."""
    tools_df = pd.read_csv(path_cwd / "inventory" / "output" / "filtered.csv")
    mapping = {}
    for repo in repos:
        url = (
            repo.lower()
            .replace("gh:", "https://github.com/")
            .replace("gl:", "https://gitlab.com/")
        )
        match = tools_df.loc[tools_df.url == url]
        if not match.empty:
            tool_name = match.iloc[0]["name"].split(",")[0]
            mapping[url] = {"repo": repo, "name": tool_name}
    return mapping


# ============================================================================
# User Interaction Analysis Functions
# ============================================================================


def render_user_interaction_analysis(tool_url: str, tool_name: str, container):
    """Render user interaction analysis for a single tool."""
    user_stats_df = load_user_classifications()
    repo = tool_url.replace("https://github.com/", "gh:").replace("https://gitlab.com/", "gl:")

    user_in_repos = user_stats_df.repos.str.contains(repo, case=False, na=False)
    filtered_df = user_stats_df[user_in_repos]

    if filtered_df.empty:
        container.info("No user interaction data available.")
        return

    # User pie chart
    class_counts = filtered_df.classification.value_counts()
    fig = px.pie(
        values=class_counts.values,
        names=class_counts.index,
        title=f"{len(filtered_df)} Users by Type",
        color_discrete_sequence=px.colors.qualitative.Plotly,
    )
    fig.update_layout(height=250, margin=dict(t=40, b=0, l=0, r=0))
    container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)

    # Top organizations
    if filtered_df.company.notna().any():
        org_counts = filtered_df.company.value_counts().head(5)
        if not org_counts.empty:
            container.markdown("**Top Organizations**")
            for org, count in org_counts.items():
                container.text(f"• {org}: {count}")

    # Top locations
    if filtered_df.location.notna().any():
        locations_count = filtered_df.location.value_counts().head(5)
        if not locations_count.empty:
            container.markdown("**Top Locations**")
            for loc, count in locations_count.items():
                container.text(f"• {loc}: {count}")


# ============================================================================
# Project Development Metrics Functions
# ============================================================================


def render_project_development_metrics(tool_url: str, tool_name: str, container):
    """Render project development metrics for a single tool."""
    df = load_repo_interactions()

    # Filter for selected tool
    repo = tool_url.replace("https://github.com/", "gh:").replace("https://gitlab.com/", "gl:")
    filtered_df = df[df.repo.str.contains(repo, case=False)]

    # Hide bots
    bot_patterns = [
        "-bot",
        r"\[bot\]",
        "actions",
        "dependabot",
        "pre-commit-ci",
    ]
    mask = ~filtered_df["username"].str.contains("|".join(bot_patterns), case=False, na=False)
    filtered_df = filtered_df[mask]

    if filtered_df.empty:
        container.info("No development metrics available.")
        return

    # Top contributors
    container.markdown("**Top 5 Contributors**")
    top_users = (
        filtered_df.loc[filtered_df["interaction"].isin(["pr", "issue", "commit"]), "username"]
        .value_counts()
        .head(5)
        .reset_index()
    )
    top_users.columns = ["username", "count"]

    for idx, row in top_users.iterrows():
        avatar_url = f"https://github.com/{row['username']}.png?size=80"
        profile_url = f"https://github.com/{row['username']}"
        container.markdown(
            f"[![{row['username']}]({avatar_url})]({profile_url}) "
            f"**[{row['username']}]({profile_url})** - {row['count']} interactions"
        )


# ============================================================================
# OSSF Scores Functions
# ============================================================================


def score_to_gradient(score_str: str) -> str:
    """Convert score to CSS gradient."""
    if str(score_str).strip() in ("?", "N/A", ""):
        return "background: #f0f0f0; color: #888;"
    try:
        value = float(str(score_str).strip())
    except (ValueError, AttributeError):
        return "background: #f0f0f0; color: #888;"
    if value >= 8:
        return "background: linear-gradient(135deg, #d4edda, #a8d5b5); color: #1a6b3a;"
    elif value >= 5:
        return "background: linear-gradient(135deg, #fff3cd, #ffe08a); color: #856404;"
    else:
        return "background: linear-gradient(135deg, #fde8e8, #f5b7b7); color: #a93226;"


def render_ossf_scores(tool_url: str, tool_name: str, container):
    """Render OSSF security scores for a single tool."""
    scores, reasons = load_ossf_scores()

    # Map URL to tool ID
    tools_df = pd.read_csv(path_cwd / "inventory" / "output" / "filtered.csv")
    match = tools_df.loc[tools_df.url == tool_url]

    if match.empty:
        container.info("No OSSF score data available.")
        return

    tool_id = match.index[0]
    if tool_id not in scores.index:
        container.info("No OSSF score data available.")
        return

    score_row = scores.loc[tool_id]
    agg = score_row.get("aggregated_score", "?")
    agg_style = score_to_gradient(agg)
    html_url = score_row.get("html_url", "#")

    # Display aggregated score
    header_html = f"""
    <div style="padding: 15px; border-radius: 5px; {agg_style} text-align: center; margin-bottom: 15px;">
        <strong>Aggregated Score: {agg}/10</strong>
    </div>
    """
    container.markdown(header_html, unsafe_allow_html=True)

    # Display top 5 checks
    check_cols = [c for c in scores.columns if c not in ("html_url", "aggregated_score")]
    check_scores = []
    for check in check_cols:
        try:
            val = float(score_row.get(check, -1))
            if val >= 0:
                check_scores.append((check, val))
        except (ValueError, TypeError):
            pass

    if check_scores:
        check_scores.sort(key=lambda x: x[1])
        container.markdown("**Lowest Scoring Checks:**")
        for check, score in check_scores[:5]:
            color = "🔴" if score < 5 else "🟡" if score < 8 else "🟢"
            container.text(f"{color} {check}: {score:.1f}/10")


# ============================================================================
# Download Trends Functions
# ============================================================================


def render_download_trends(tool_url: str, tool_name: str, container):
    """Render download trends for a single tool."""
    df = load_downloads()
    tools_df = pd.read_csv(path_cwd / "inventory" / "output" / "filtered.csv")

    # Map URL to tool ID
    match = tools_df.loc[tools_df.url == tool_url]
    if match.empty:
        container.info("No download data available.")
        return

    tool_id = match.index[0]
    tool_df = df[df["id"] == tool_id]

    if tool_df.empty:
        container.info("No download data available.")
        return

    trend_df = tool_df.sort_values("date")

    # Show recent stats
    if len(trend_df) >= 3:
        recent = trend_df.tail(3)
        container.markdown("**Recent Downloads (last 3 months):**")
        for _, row in recent.iterrows():
            container.text(f"• {row['date'].strftime('%b %Y')}: {int(row['downloads']):,}")

    # Plot trends
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=trend_df["date"],
            y=trend_df["downloads"],
            mode="lines+markers",
            line=dict(color="#0173B2", width=2),
            fill="tozeroy",
            fillcolor="rgba(1, 115, 178, 0.1)",
        )
    )

    fig.update_layout(
        template="plotly_white",
        height=250,
        margin=dict(t=20, b=40, l=10, r=10),
        xaxis=dict(title="Month", showgrid=False),
        yaxis=dict(title="Downloads", tickformat=","),
        hovermode="x",
        showlegend=False,
    )
    container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)


# ============================================================================
# Main App
# ============================================================================


def main():
    """Main function."""
    st.set_page_config(page_title="Tool Deep Dive", page_icon="🔍", layout="wide")
    st.title("🔍 Tool Deep Dive")

    # Get selected tools from session state
    selected_names = util.get_state("selected_tool_names", [])
    selected_urls = util.get_state("selected_tool_urls", [])

    if not selected_names:
        st.info(
            "👈 Please select tools from the main page table to view detailed analysis here."
        )
        st.markdown(
            """
            ### How to use this page:
            1. Go to the main **Tool Repository Metrics** page
            2. Use the filters to find tools of interest
            3. Select up to 3 tools by clicking on the rows in the table
            4. Return to this page to see the detailed analysis
            """
        )
        return

    # Display selected tools
    st.markdown(f"**Analyzing {len(selected_names)} tool(s):** {', '.join(selected_names)}")
    st.markdown("---")

    # Create columns for each tool
    if len(selected_names) == 1:
        cols = [st.container()]
    elif len(selected_names) == 2:
        cols = st.columns(2)
    else:
        cols = st.columns(3)

    # Render each analysis section for each tool side by side
    for idx, (name, url) in enumerate(zip(selected_names, selected_urls)):
        with cols[idx]:
            st.markdown(f"### {name}")

            with st.expander("👤 User Interactions", expanded=True):
                render_user_interaction_analysis(url, name, st.container())

            with st.expander("📊 Development Metrics", expanded=True):
                render_project_development_metrics(url, name, st.container())

            with st.expander("🔐 Security Score", expanded=True):
                render_ossf_scores(url, name, st.container())

            with st.expander("📦 Downloads", expanded=True):
                render_download_trends(url, name, st.container())


if __name__ == "__main__":
    main()
