# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Unified deep dive page combining all tool analyses."""

from pathlib import Path

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
    # Add explanatory text
    container.markdown(
        """
        A wide variety of users interact with the hosted repositories of each of our tracked energy modelling tools. On this page, you can explore these interactions for all GitHub-hosted tools.

        Interactions generally come in the form of
        [stars](https://docs.github.com/en/get-started/exploring-projects-on-github/saving-repositories-with-stars),
        [forks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-forks),
        [watches](https://dl.acm.org/doi/10.1145/2597073.2597114),
        [issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/about-issues), and
        [contributions](https://docs.github.com/en/repositories/viewing-activity-and-data-for-your-repository/viewing-a-projects-contributors#about-contributors).
        We have gathered data on the GitHub users linked to those interactions to find their origin country and attempted to classify them as being from one of 7 main groups:

        🎓 **academic** - an academic institution (e.g., university).

        🏦 **financial** - a financial institution (e.g., bank).

        🏬 **government** - a government department.

        🏭 **industry** - an energy industry actor (e.g., wind turbine manufacturer).

        👩‍💻 **professional** - a consultancy / professional interest group (incl. self-employed).

        🔎 **research** - a non-academic research institution (e.g., a US national lab).

        💡 **utility** - an energy industry public/private utility company or system operator (e.g., a transmission system operator)

        Here, you can explore the result of our user interaction analysis for this tool. In doing so, you may find out more about:

        - how much interaction a tool is getting within and outside academia.
        - which organisations are most involved with a tool.
        - the geographic diversity of tool interaction, especially how far the reach of the tool is beyond its "home" country.

        Whether you're a tool maintainer looking to understand your reach, a potential tool user exploring the size of the community in your country, or a financier quantifying the value of investing in tool development, we hope you find this analysis interesting!
        """
    )

    with container.expander("Caveats", icon="⚠️"):
        st.markdown(
            """
            1. Tool repository interactions do not tell the whole story.
            There is usually an order of magnitude more downloads of a tool per month than the total number of unique user interactions on a tool repository over its lifetime.
            These interactions therefore only tell us about individuals who have a GitHub account and have navigated directly to the tool source code - they may not even use the tool!
            Understanding more about tool users for open source projects is generally not possible; there is no obligation on users to identify themselves when downloading a tool, nor should there be.

            2. We rely on a heuristic approach to classify users based on the data they choose to share on GitHub.
            This means that we are unable to classify more than 50% of users and will inevitably misclassify some of them with our relatively simple string matching approach.

            This analysis may raise more questions than it answers.
            Still, by raising these questions we hope to foster further discussions on tools and their use.
            """
        )

    user_stats_df = load_user_classifications()

    # Convert URL to repo format
    repo = tool_url.replace("https://github.com/", "gh:").replace(
        "https://gitlab.com/", "gl:"
    )

    # Filter users who interacted with this repo
    user_in_repos = user_stats_df.repos.str.contains(repo, case=False, na=False)
    filtered_df = user_stats_df[user_in_repos]

    if filtered_df.empty:
        container.info("No user interaction data available for this tool.")
        return

    # User classification pie chart
    container.markdown("### User Types Across All Repositories")
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
            title="Top 10 Organizations",
            color="Number of Users",
            color_continuous_scale=px.colors.sequential.Viridis,
        )
        fig.update_layout(
            xaxis_tickangle=-45, xaxis={"title": "Organization"}, height=350
        )
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
            title="Top 10 Locations",
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
                showframe=True, showcoastlines=True, projection_type="equirectangular"
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
    # Add explanatory text
    container.markdown(
        """
        Activity on source code repositories can tell us about how tools are being developed and maintained.
        Here we analyse interactions on GitHub repositories for energy modelling tools, including
        [stars](https://docs.github.com/en/get-started/exploring-projects-on-github/saving-repositories-with-stars),
        [forks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-forks),
        [issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/about-issues),
        [pull requests (PRs)](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests),
        and [commits](https://docs.github.com/en/pull-requests/committing-changes-to-your-project/creating-and-editing-commits/about-commits).
        We also look at key contributors to these repositories.
        Together, this information can help us understand how actively a tool is being developed, how responsive maintainers are to feedback, and how engaged the community is around a tool's development.
        """
    )

    df = load_repo_interactions()

    # Convert URL to repo format
    repo = tool_url.replace("https://github.com/", "gh:").replace(
        "https://gitlab.com/", "gl:"
    )
    filtered_df = df[df.repo.str.contains(repo, case=False)]

    # Hide bots
    bot_patterns = ["-bot", r"\[bot\]", "actions", "dependabot", "pre-commit-ci"]
    mask = ~filtered_df["username"].str.contains(
        "|".join(bot_patterns), case=False, na=False
    )
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
            | (
                filtered_df.interaction.isin(["issue", "pr"])
                & (filtered_df.subtype == "author")
            )
        ],
        "created",
        resample,
    )

    plot_df = (
        totals_df.cumsum()
        .ffill()
        .stack()
        .rename_axis(index=["Date", "Interaction"])
        .to_frame("Count")
        .reset_index()
    )

    colors = px.colors.sequential.Peach
    fig = px.bar(
        plot_df,
        x="Date",
        y="Count",
        color="Interaction",
        title=f"Cumulative Repository Metrics ({resolution})",
        color_discrete_map={
            metric: colors[idx % len(colors)]
            for idx, metric in enumerate(
                [
                    "Total Commits",
                    "Total Stars",
                    "Total Forks",
                    "Total Issues",
                    "Total PRs",
                ]
            )
        },
    )
    fig.update_layout(hovermode="x", height=350)
    container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)

    # Top contributors
    container.markdown("### Top 10 Contributors")
    top_users = (
        filtered_df.loc[
            filtered_df["interaction"].isin(["pr", "issue", "commit"]), "username"
        ]
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
    # Add explanatory text
    container.markdown(
        """
        The [OpenSSF Scorecard](https://github.com/ossf/scorecard?tab=readme-ov-file#what-is-scorecard) provides a detailed view of security practices for this tool.
        The scores are colour-coded to help you quickly identify areas of strength and weakness in the security posture of the tool.
        The scores shown below are on a scale from **0 to 10**, where **10** represents the highest level of security compliance.

        Select individual checks to see detailed reasons for any failed or low-scoring checks.
        """
    )

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
    check_cols = [
        c for c in scores.columns if c not in ("html_url", "aggregated_score")
    ]
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
    # Add explanatory text
    container.markdown(
        """
        Package downloads are a strong proxy for **real-world tool usage** as they capture users who actually install and run a tool.

        Here we track **monthly PyPI and Conda downloads** for energy modelling tools that publish Python packages, spanning the past year.
        """
    )

    with container.expander("ℹ️ Notes on the data"):
        st.markdown(
            """
            - **PyPI and Conda only.** Tools distributed exclusively via Julia's General
              registry, Maven Central, or other ecosystems are not reflected here.
            - **Bot & CI traffic.** Automated downloads by CI pipelines are not considered in this infographic for PyPI.
            - **No current month.** The current month is not shown as the complete data is not yet available.
            """
        )

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
            3. Select one tool by clicking on a row in the table
            4. Return to this page to see the detailed analysis
            """
        )
        st.stop()

    # Display single tool analysis
    tool_name = selected_names[0]
    tool_url = selected_urls[0]

    st.markdown(f"## Analyzing: **{tool_name}**")
    st.markdown("---")

    # User Interactions
    with st.expander("👤 Tool User Interaction Analysis", expanded=True):
        render_user_interaction_section(tool_url, tool_name, st.container())

    st.markdown("---")

    # Development Metrics
    with st.expander("📊 Project Development Metrics", expanded=True):
        render_project_development_section(tool_url, tool_name, st.container())

    st.markdown("---")

    # OSSF Scores
    with st.expander("🔐 OpenSSF Security Scores", expanded=True):
        render_ossf_section(tool_url, tool_name, st.container())

    st.markdown("---")

    # Downloads
    with st.expander("📦 Download Trends", expanded=True):
        render_downloads_section(tool_url, tool_name, st.container())
