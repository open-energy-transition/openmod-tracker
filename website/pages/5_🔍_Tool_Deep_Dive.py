# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Unified deep dive page combining all tool analyses."""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import util

# Configuration
FIG_CONFIG = {"displayModeBar": False, "doubleClick": False, "scrollZoom": False}
RESOLUTION_CONVERTER = {"Daily": "D", "Weekly": "W", "Monthly": "ME"}

# Paths
path_cwd = Path.cwd()
user_stats_dir = path_cwd / "user_analysis" / "output"
inventory_dir = path_cwd / "inventory" / "output"


# ============================================================================
# Data Loading Functions
# ============================================================================


@st.cache_data
def load_tools_mapping() -> pd.DataFrame:
    """Load tools mapping data."""
    return pd.read_csv(inventory_dir / "filtered.csv", index_col="id")


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
    scores = pd.read_csv(inventory_dir / "scores.csv", index_col="id")
    reasons = pd.read_csv(inventory_dir / "reasons.csv", index_col="id")
    return scores, reasons


@st.cache_data
def load_downloads() -> pd.DataFrame:
    """Load package downloads data."""
    import re

    raw = pd.read_csv(user_stats_dir / "package_downloads.csv")
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


def get_tool_id_from_url(url: str) -> str | None:
    """Get tool ID from URL."""
    tools_df = load_tools_mapping()
    match = tools_df[tools_df.url == url]
    if not match.empty:
        return match.index[0]
    return None


# ============================================================================
# User Interaction Analysis
# ============================================================================


def render_user_interaction_section(tool_url: str, tool_name: str, container):
    """Render complete user interaction analysis."""
    user_stats_df = load_user_classifications()

    # Convert URL to repo format
    repo = tool_url.replace("https://github.com/", "gh:").replace("https://gitlab.com/", "gl:")

    # Filter users who interacted with this repo
    user_in_repos = user_stats_df.repos.str.contains(repo, case=False, na=False)
    filtered_df = user_stats_df[user_in_repos]

    if filtered_df.empty:
        container.info("No user interaction data available for this tool.")
        return

    # User classification pie chart
    class_counts = filtered_df.classification.value_counts()
    fig = px.pie(
        values=class_counts.values,
        names=class_counts.index,
        title=f"Distribution of {len(filtered_df)} Users by Type",
        color_discrete_sequence=px.colors.qualitative.Plotly,
    )
    fig.update_layout(height=300)
    container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)

    # Top organizations
    container.markdown("### Top Organizations Engaging with Repository")
    org_counts = filtered_df.company.value_counts().head(10)
    if not org_counts.empty:
        fig = px.bar(
            org_counts.to_frame("Number of Users").reset_index(),
            x="company",
            y="Number of Users",
            title=f"Top 10 Organizations",
            color="Number of Users",
            color_continuous_scale=px.colors.sequential.Viridis,
        )
        fig.update_layout(xaxis_tickangle=-45, xaxis={"title": "Organization"}, height=350)
        container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)
    else:
        container.info("No organization data available.")

    # Top locations
    if filtered_df.location.notna().any():
        container.markdown("### Top User Origin Countries")
        locations_count = filtered_df.location.value_counts().head(10)
        fig = px.bar(
            locations_count.to_frame("Number of Users").reset_index(),
            x="location",
            y="Number of Users",
            title=f"Top 10 Locations",
            color="Number of Users",
            color_continuous_scale=px.colors.sequential.Viridis,
        )
        fig.update_layout(xaxis_tickangle=-45, xaxis={"title": "Location"}, height=350)
        container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)

        # Geographic map
        container.markdown("### Geographic Map")
        fig = px.choropleth(
            locations_count.rename_axis(index="country")
            .to_frame("Number of Users")
            .reset_index(),
            locations="country",
            locationmode="ISO-3",
            color="Number of Users",
            hover_name="country",
            color_continuous_scale=px.colors.sequential.Viridis,
            title="Users by location",
        )
        fig.update_layout(
            geo=dict(
                showframe=True,
                showcoastlines=True,
                projection_type="equirectangular",
            ),
            height=400,
        )
        container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)


# ============================================================================
# Project Development Metrics
# ============================================================================


def get_totals(df: pd.DataFrame, date_col: str, resample: str) -> pd.DataFrame:
    """Calculate counts of interactions over time."""
    totals_df = (
        df.groupby(["interaction", date_col])
        .size()
        .unstack("interaction")
        .resample(resample)
        .sum()
        .rename(
            columns={
                "fork": "Total Forks",
                "stargazer": "Total Stars",
                "issue": "Total Issues",
                "pr": "Total PRs",
                "commit": "Total Commits",
            }
        )
    )
    return totals_df


def render_project_development_section(tool_url: str, tool_name: str, container):
    """Render complete project development metrics."""
    df = load_repo_interactions()
    user_class_df = load_user_classifications()

    # Convert URL to repo format
    repo = tool_url.replace("https://github.com/", "gh:").replace("https://gitlab.com/", "gl:")
    filtered_df = df[df.repo.str.contains(repo, case=False)]

    # Hide bots
    bot_patterns = ["-bot", r"\[bot\]", "actions", "dependabot", "pre-commit-ci"]
    mask = ~filtered_df["username"].str.contains("|".join(bot_patterns), case=False, na=False)
    filtered_df = filtered_df[mask]

    if filtered_df.empty:
        container.info("No development metrics available for this tool.")
        return

    # Repository metrics over time
    container.markdown("### Repository Metrics Over Time")
    resolution = "Weekly"
    resample = f"1{RESOLUTION_CONVERTER[resolution]}"

    # Cumulative metrics
    totals_df = get_totals(
        filtered_df[
            filtered_df.interaction.isin(["fork", "commit", "stargazer"])
            | (filtered_df.interaction.isin(["issue", "pr"]) & (filtered_df.subtype == "author"))
        ],
        "created",
        resample,
    )

    plot_df = totals_df.cumsum().ffill().stack().rename_axis(index=["Date", "Interaction"]).to_frame("Count").reset_index()

    colors = px.colors.sequential.Peach
    fig = px.bar(
        plot_df,
        x="Date",
        y="Count",
        color="Interaction",
        title=f"Cumulative Repository Metrics ({resolution})",
        color_discrete_map={
            metric: colors[idx % len(colors)]
            for idx, metric in enumerate(["Total Commits", "Total Stars", "Total Forks", "Total Issues", "Total PRs"])
        },
    )
    fig.update_layout(hovermode="x", height=350)
    container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)

    # Top contributors
    container.markdown("### Top 10 Contributors")
    top_users = (
        filtered_df.loc[filtered_df["interaction"].isin(["pr", "issue", "commit"]), "username"]
        .value_counts()
        .head(10)
        .reset_index()
    )
    top_users.columns = ["username", "count"]

    cols = container.columns(5)
    for idx, row in top_users.iterrows():
        with cols[idx % 5]:
            avatar_url = f"https://github.com/{row['username']}.png?size=160"
            profile_url = f"https://github.com/{row['username']}"
            st.image(
                avatar_url,
                width=100,
                caption=f"[{row['username']}]({profile_url})\n\n{row['count']} interactions",
            )


# ============================================================================
# OSSF Security Scores
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


def render_ossf_section(tool_url: str, tool_name: str, container):
    """Render OSSF security scores."""
    scores, reasons = load_ossf_scores()
    tool_id = get_tool_id_from_url(tool_url)

    if not tool_id or tool_id not in scores.index:
        container.info("No OSSF score data available for this tool.")
        return

    score_row = scores.loc[tool_id]
    agg = score_row.get("aggregated_score", "?")
    agg_style = score_to_gradient(agg)

    # Display aggregated score
    header_html = f"""
    <div style="padding: 20px; border-radius: 8px; {agg_style} text-align: center; margin-bottom: 20px;">
        <h3 style="margin: 0;">Aggregated Security Score</h3>
        <h1 style="margin: 10px 0;">{agg}/10</h1>
    </div>
    """
    container.markdown(header_html, unsafe_allow_html=True)

    # Display individual checks
    check_cols = [c for c in scores.columns if c not in ("html_url", "aggregated_score")]
    check_data = []
    for check in check_cols:
        try:
            val = float(score_row.get(check, -1))
            if val >= 0:
                check_data.append({"Check": check, "Score": val})
        except (ValueError, TypeError):
            pass

    if check_data:
        check_df = pd.DataFrame(check_data).sort_values("Score")
        container.markdown("### Security Check Scores")
        for _, row in check_df.iterrows():
            score_val = row["Score"]
            if score_val >= 8:
                color = "🟢"
            elif score_val >= 5:
                color = "🟡"
            else:
                color = "🔴"
            container.text(f"{color} {row['Check']}: {score_val:.1f}/10")


# ============================================================================
# Download Trends
# ============================================================================


def render_downloads_section(tool_url: str, tool_name: str, container):
    """Render download trends."""
    df = load_downloads()
    tool_id = get_tool_id_from_url(tool_url)

    if not tool_id:
        container.info("No download data available for this tool.")
        return

    tool_df = df[df["id"] == tool_id]

    if tool_df.empty:
        container.info("No download data available for this tool.")
        return

    trend_df = tool_df.sort_values("date")

    # Show recent stats
    container.markdown("### Recent Monthly Downloads")
    if len(trend_df) >= 6:
        recent = trend_df.tail(6)
        cols = container.columns(3)
        for idx, (_, row) in enumerate(recent.iterrows()):
            with cols[idx % 3]:
                st.metric(
                    label=row["date"].strftime("%b %Y"),
                    value=f"{int(row['downloads']):,}",
                )

    # Plot trends
    container.markdown("### Download Trend")
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
        height=350,
        xaxis=dict(title="Month"),
        yaxis=dict(title="Downloads", tickformat=","),
        hovermode="x",
        showlegend=False,
    )
    container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)


if __name__ == "__main__":
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
        st.stop()

    st.markdown(f"**Analyzing {len(selected_names)} tool(s):** {', '.join(selected_names)}")
    st.markdown("---")

    # Create columns based on number of tools
    if len(selected_names) == 1:
        cols = [st.container()]
    elif len(selected_names) == 2:
        cols = st.columns(2)
    else:
        cols = st.columns(3)

    # Render each tool's analysis
    for idx, (name, url) in enumerate(zip(selected_names, selected_urls)):
        with cols[idx]:
            st.markdown(f"## {name}")

            # User Interactions
            with st.expander("👤 User Interaction Analysis", expanded=True):
                render_user_interaction_section(url, name, st.container())

            # Development Metrics
            with st.expander("📊 Project Development Metrics", expanded=True):
                render_project_development_section(url, name, st.container())

            # OSSF Scores
            with st.expander("🔐 OpenSSF Security Scores", expanded=True):
                render_ossf_section(url, name, st.container())

            # Downloads
            with st.expander("📦 Download Trends", expanded=True):
                render_downloads_section(url, name, st.container())
