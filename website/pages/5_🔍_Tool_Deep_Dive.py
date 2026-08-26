# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Unified deep dive page combining all tool analyses."""

import re
from pathlib import Path
from typing import Any

import jinja2
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

TOTALS_METRICS = [
    "Total Commits",
    "Total Stars",
    "Total Forks",
    "Total Issues",
    "Total PRs",
]
OPEN_METRICS = [
    "Open Issues",
    "Open PRs",
    "New Issue Comments",
    "New PR Comments",
    "New PR Reviews",
]

# Paths
path_cwd = Path.cwd()
user_stats_dir = path_cwd / "user_analysis" / "output"
inventory_dir = path_cwd / "inventory" / "output"

# ── Jinja2 environment ────────────────────────────────────────────────────────
_templates_dir = path_cwd / "website" / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_templates_dir)),
    autoescape=jinja2.select_autoescape(["html"]),
)

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


def _reindex_to_daterange(
    df: pd.DataFrame, resample: str, tool_name: str
) -> pd.DataFrame:
    """Reindex dataframe to match the date range from the slider."""
    date_range_key = f"date_range_picker_{tool_name}"
    if date_range_key in st.session_state:
        start_date, end_date = st.session_state[date_range_key]
        return df.reindex(pd.date_range(start_date, end_date, freq=resample))
    return df


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


def render_user_interaction_section(
    tool_url: str, tool_name: str, container: Any
) -> None:
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

    # Render glowy header
    header_template = _jinja_env.get_template("user_interaction_header.html.jinja")
    header_html = header_template.render(
        html_url=tool_url, selected_tool=tool_name, total_users=len(filtered_df)
    )
    container.markdown(header_html, unsafe_allow_html=True)

    # User classification bar chart
    container.markdown("### User Types Across All Repositories")
    class_counts = filtered_df.classification.value_counts()
    fig = px.bar(
        class_counts.to_frame("Number of Users").reset_index(),
        y="classification",
        x="Number of Users",
        title=f"Distribution of {len(filtered_df)} Users by Type",
        orientation="h",
        text="Number of Users",
    )
    fig.update_traces(texttemplate="%{text}", textposition="outside")
    fig.update_layout(
        height=300,
        showlegend=False,
        yaxis={"title": "User Type"},
        xaxis={"title": "Number of Users", "gridcolor": "rgba(0,0,0,0.07)"},
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=40),
    )
    container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)

    # Top organizations
    container.markdown("### Top Organizations Engaging with Repository")
    org_counts = filtered_df.company.value_counts().head(KEEP_TOP)
    if not org_counts.empty:
        fig = px.bar(
            org_counts.to_frame("Number of Users").reset_index(),
            y="company",
            x="Number of Users",
            title=f"Top {KEEP_TOP} Organizations",
            orientation="h",
            text="Number of Users",
        )
        fig.update_traces(texttemplate="%{text}", textposition="outside")
        fig.update_layout(
            yaxis={"title": "Organization"},
            xaxis={"title": "Number of Users", "gridcolor": "rgba(0,0,0,0.07)"},
            height=350,
            template="plotly_white",
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(l=10, r=10, t=50, b=40),
        )
        container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)
    else:
        container.info("No organization data available.")

    # Top locations
    if filtered_df.location.notna().any():
        container.markdown("### Top User Origin Countries")
        user_origin_count = filtered_df.location.value_counts().head(KEEP_TOP)
        fig = px.bar(
            user_origin_count.to_frame("Number of Users").reset_index(),
            y="location",
            x="Number of Users",
            title=f"Top {KEEP_TOP} Locations",
            orientation="h",
            text="Number of Users",
        )
        fig.update_traces(texttemplate="%{text}", textposition="outside")
        fig.update_layout(
            yaxis={"title": "Location"},
            xaxis={"title": "Number of Users", "gridcolor": "rgba(0,0,0,0.07)"},
            height=350,
            template="plotly_white",
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(l=10, r=10, t=50, b=40),
        )
        container.plotly_chart(fig, use_container_width=True, config=FIG_CONFIG)

        # Geographic map
        container.markdown("### Geographic Map")
        locations_count = filtered_df.location.value_counts()
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
                landcolor="rgb(243, 243, 243)",  # Light gray land
                oceancolor="rgb(220, 240, 255)",  # Light blue ocean
                coastlinecolor="rgb(80, 80, 80)",  # Darker coast lines
                countrycolor="rgb(150, 150, 150)",  # Gray country borders
            ),
            margin=dict(l=0, r=0, t=50, b=0),  # Tight margins
            paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
            plot_bgcolor="rgba(0,0,0,0)",  # Transparent plot area
        )
        container.plotly_chart(
            fig, use_container_width=True, config=FIG_CONFIG, key="country_map"
        )


# ============================================================================
# Project Development Metrics
# ============================================================================


def date_filter(df: pd.DataFrame, date_range: tuple[str, str]) -> pd.DataFrame:
    """Filter DataFrame by date range.

    Args:
        df: DataFrame to filter.
        date_range: Start and end dates (YYYY-MM-DD) for filtering.

    Returns:
        Filtered DataFrame.
    """
    for dt_col in ["created", "closed", "merged"]:
        df = df[df[dt_col].fillna(df.created).between(*date_range)]

    return df


def get_totals(df: pd.DataFrame, date_col: str, resample: str) -> pd.DataFrame:
    """Calculate counts of interactions over time.

    Args:
        df: DataFrame containing interaction data.
        date_col: Name of the date column to use for resampling.
        resample: Resampling frequency string (e.g., '1D', '1W', '1ME').

    Returns:
        DataFrame with interaction counts over time.
    """
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


def _plot_timeseries(
    df: pd.DataFrame,
    color_map: dict,
    title: str,
    category_orders: dict,
    plot_type: str = "bar",
) -> go.Figure:
    """Create a timeseries plot for interaction metrics.

    Args:
        df: DataFrame containing interaction data with Date, Count, and Interaction columns.
        color_map: Dictionary mapping interaction types to colors.
        title: Title for the plot.
        category_orders: Dictionary defining the order of categories for plotting.
        plot_type: Type of plot to create ('bar' or 'line'). Defaults to 'bar'.

    Returns:
        Plotly Figure object.
    """
    plotter = getattr(px, plot_type)
    fig = plotter(
        df,
        x="Date",
        y="Count",
        color="Interaction",
        title=title,
        color_discrete_map=color_map,
        category_orders=category_orders,
    )
    fig.update_traces(hovertemplate=None)
    fig.update_layout(
        hovermode="x",
        xaxis=dict(type="date"),
        dragmode=False,
        legend=dict(
            yanchor="bottom", xanchor="center", orientation="h", x=0.5, y=1, title=None
        ),
    )
    return fig


def plot_totals_metrics(
    df: pd.DataFrame,
    resolution: str,
    color_map: dict,
    cumulative: bool = True,
    tool_name: str = "",
) -> go.Figure:
    """Create cumulative metrics timeline chart.

    Args:
        df: DataFrame containing interaction data.
        resolution: Time resolution for resampling ('Daily', 'Weekly', or 'Monthly').
        color_map: Dictionary mapping metric names to colors.
        cumulative: Whether to show cumulative counts. Defaults to True.
        tool_name: Tool name for accessing session state. Defaults to "".

    Returns:
        Plotly Figure showing cumulative repository metrics over time.
    """
    resample = f"1{RESOLUTION_CONVERTER[resolution]}"
    totals_df = get_totals(
        df[
            df.interaction.isin(["fork", "commit", "stargazer"])
            | (df.interaction.isin(["issue", "pr"]) & (df.subtype == "author"))
        ],
        "created",
        resample,
    )
    totals_df = totals_df.assign(
        **{col: 0 for col in set(TOTALS_METRICS).difference(totals_df.columns)}
    )
    if cumulative:
        totals_df_filled = totals_df.cumsum().ffill().fillna(0)
    else:
        totals_df_filled = totals_df.fillna(0)

    # Apply date range filter to display
    totals_df_filled = _reindex_to_daterange(totals_df_filled, resample, tool_name)

    plot_df = (
        totals_df_filled.stack()
        .rename_axis(index=["Date", "Interaction"])
        .to_frame("Count")
        .reset_index()
    )
    title_prefix = "Cumulative " if cumulative else ""
    fig = _plot_timeseries(
        plot_df,
        color_map,
        title=f"{title_prefix}Repository Metrics Over Time ({resolution})",
        category_orders={"Interaction": TOTALS_METRICS},
    )
    return fig


def plot_open_metrics(
    df: pd.DataFrame, resolution: str, color_map: dict, tool_name: str = ""
) -> go.Figure:
    """Create open issues and PRs timeline chart.

    Args:
        df: DataFrame containing interaction data.
        resolution: Time resolution for resampling ('Daily', 'Weekly', or 'Monthly').
        color_map: Dictionary mapping metric names to colors.
        tool_name: Tool name for accessing session state. Defaults to "".

    Returns:
        Plotly Figure showing open issues and PRs over time.
    """
    resample = f"1{RESOLUTION_CONVERTER[resolution]}"
    _df = df.loc[
        df["interaction"].isin(["issue", "pr"]) & (df["subtype"] == "author")
    ].copy()
    _df["closed"] = _df["closed"].fillna(_df["merged"])
    _df_unique = _df.drop_duplicates(subset=["number"])
    created_df = get_totals(_df_unique, "created", resample).cumsum()
    closed_df = get_totals(_df_unique, "closed", resample).cumsum()
    closed_df_full = closed_df.reindex(created_df.index).ffill().fillna(0)
    open_df = (
        created_df.subtract(closed_df_full)
        .rename(columns=lambda x: x.replace("Total ", "Open "))
        .fillna(0)
    )

    extra_dfs = []
    for subtype in ["comment", "review"]:
        _df = get_totals(
            df.loc[
                df["interaction"].isin(["issue", "pr"]) & (df["subtype"] == subtype)
            ],
            "created",
            resample,
        ).rename(
            columns=lambda x: (
                x.replace("Total ", "New ").removesuffix("s") + f" {subtype.title()}s"
            )
        )
        extra_dfs.append(_df)
    all_df = pd.concat([open_df, *extra_dfs], axis=1)
    all_df = all_df.assign(
        **{col: 0 for col in set(OPEN_METRICS).difference(all_df.columns)}
    )
    all_df = all_df.fillna(
        {
            "Open Issues": all_df.get("Open Issues", pd.Series()).ffill(),
            "Open PRs": all_df.get("Open PRs", pd.Series()).ffill(),
            "New Issue Comments": 0,
            "New PR Comments": 0,
            "New PR Reviews": 0,
        }
    )

    # Apply date range filter to display
    all_df = _reindex_to_daterange(all_df, resample, tool_name)

    plot_df = (
        all_df.stack()
        .rename_axis(index=["Date", "Interaction"])
        .to_frame("Count")
        .reset_index()
    )

    fig = _plot_timeseries(
        plot_df,
        color_map,
        title=f"Open Issues and PRs ({resolution})",
        category_orders={"Interaction": OPEN_METRICS},
    )
    return fig


def exclude_bot_interactions(df: pd.DataFrame, hide_bots: bool = True) -> pd.DataFrame:
    """Filter out interactions by bots.

    Args:
        df: DataFrame containing user interaction data.
        hide_bots: Whether to filter out bot interactions. Defaults to True.

    Returns:
        Filtered DataFrame containing interactions matching the criteria.
    """
    bot_patterns = [
        "-bot",
        r"\[bot\]",
        "actions",
        "dependabot",
        "JuliaTagBot",
        "pudlbot",
        "codebot",
        "renovate",
        "sonarqube",
        "codecov",
        "coveralls",
        "pre-commit-ci",
        "pull-request-size",
        "copilot",
        "github-advanced-security",
        "coderabbitai",
    ]
    if hide_bots:
        mask = ~df["username"].str.contains(
            "|".join(bot_patterns), case=False, na=False
        )
        df = df[mask]
    return df


def detailed_org_contributions_breakdown(
    df: pd.DataFrame, user_classifications_df: pd.DataFrame
) -> None:
    """Display detailed breakdown of organizational contributions by type.

    Shows top 3 organizations with expandable statistics in columns.

    Args:
        df (pd.DataFrame): DataFrame containing user interaction data (already filtered).
        user_classifications_df (pd.DataFrame): DataFrame containing username to company mappings.
    """
    st.subheader("Top 3 Contributing Organizations")

    contribution_types = {
        "Issues Opened": "interaction == 'issue' & subtype == 'author'",
        "PRs Opened": "interaction == 'pr' & subtype == 'author'",
        "Commits": "interaction == 'commit'",
        "Feedback Given": (
            "interaction in ['issue', 'pr'] & subtype in ['comment', 'reaction', 'review']"
        ),
    }

    global_totals = {"Total contributions": len(df)}
    for contrib_name, mask in contribution_types.items():
        global_totals[contrib_name] = len(df.query(mask))

    org_contributions = (
        df.merge(user_classifications_df[["username", "company"]], on="username")
        .groupby(["company", "interaction", "subtype"])
        .size()
        .to_frame("count")
        .reset_index()
    )

    totals = {
        "Total contributions": org_contributions.groupby("company")["count"].sum()
    }

    for contrib_name, mask in contribution_types.items():
        totals[contrib_name] = (
            org_contributions.query(mask).groupby("company")["count"].sum()
        )

    totals_df = (
        pd.DataFrame(totals)
        .fillna(0)
        .sort_values(by="Total contributions", ascending=False)
        .head(3)
    )

    st.html(
        f"""
        <style>
            div [data-testid=stExpander] details summary{{
                background-color: {px.colors.sequential.Peach[0]};
            }}
            div [data-testid=stExpander] details summary p{{
                font-size: 1rem;
            }}
        </style>
        """
    )

    cols = st.columns(3)

    metric_order = ["Issues Opened", "PRs Opened", "Commits", "Feedback Given"]

    for (company, row), col in zip(totals_df.iterrows(), cols):
        with col:
            company_name = str(company).title()

            st.markdown(f"**{company_name}**")

            st.metric(
                label="Total contributions",
                value=f"{int(row['Total contributions']):,}",
            )
            with st.expander("View breakdown"):
                for metric in metric_order:
                    st.markdown(
                        _render_stat(metric, row[metric], global_totals[metric])
                    )


def _render_stat(label: str, value: int, total: int) -> str:
    """Render an org contribution as a markdown string with percentage.

    Args:
        label (str): label for the metric.
        value (int): value for the metric.
        total (int): total value for calculating percentage.

    Returns:
        str: formatted markdown string with value and percentage.
    """
    pct = (value / total * 100) if total > 0 else 0
    return f"**{label}:** {int(value):,} / {int(total):,} ({int(pct)}%)"


def get_complete_time(df: pd.DataFrame, interaction: str, time_col: str) -> pd.Series:
    """Calculate time to completion for PRs or issues.

    Args:
        df: DataFrame containing interaction data.
        interaction: Type of interaction ('pr' or 'issue').
        time_col: Name of the completion date column ('merged' or 'closed').

    Returns:
        Series containing completion times in days.
    """
    # Calculate time to merge for PRs
    data = df.loc[(df.interaction == interaction) & (df["subtype"] == "author")].dropna(
        subset=[time_col]
    )
    complete_time = (data[time_col] - data["created"]).dt.total_seconds() / (24 * 3600)
    return complete_time


def plot_histogram(
    df: pd.Series, global_median: float | None, title: str, label: str
) -> go.Figure:
    """Create a histogram with median lines.

    Args:
        df: Series containing data to plot.
        global_median: Median value for all tools, or None.
        title: Title for the histogram.
        label: Label for the x-axis.

    Returns:
        Plotly Figure object configured with histogram and median lines.
    """
    fig = px.histogram(
        df.to_frame("count"),
        x="count",
        nbins=50,
        title=f"{title} (n={len(df)})",
        labels={"count": label},
        color_discrete_sequence=[px.colors.sequential.Peach[5]],
    )
    fig.add_vline(
        x=(median := df.median()),
        line_dash="dash",
        line_color="black",
        annotation={
            "text": f"Median: {median:.1f}",
            "font_color": "black",
            "y": 1,
            # "position": "top",
        },
    )
    if global_median is not None:
        fig.add_vline(
            x=global_median,
            line_dash="dot",
            line_color="grey",
            annotation={
                "text": f"All tools Median: {global_median:.1f}",
                "font_color": "grey",
                # "position": "bottom",
                # "ayref": "paper",
                "y": 1.05,
            },
        )
    fig.update_layout(
        xaxis_title=label,
        yaxis_title="Count",
        showlegend=False,
        bargap=0.1,
        dragmode=False,
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _get_engagement(df: pd.DataFrame, interaction: str) -> pd.Series:
    """Calculate engagement metrics for PRs or issues.

    Args:
        df: DataFrame containing interaction data.
        interaction: Type of interaction ('pr' or 'issue').

    Returns:
        Series containing engagement counts (comments, reactions, reviews) per item.
    """
    engagement = (
        df.loc[
            (df.interaction == interaction)
            & df.subtype.isin(["comment", "reaction", "review"])
        ]
        .groupby(["number", "repo"], group_keys=False)
        .size()
    )
    engagement_inc_zero = engagement.reindex(
        df.loc[(df.interaction == interaction)]
        .set_index(["number", "repo"])
        .index.drop_duplicates()
    ).fillna(0)
    return engagement_inc_zero


def resolution_histograms(
    df: pd.DataFrame, global_df: pd.DataFrame | None = None
) -> None:
    """Create histograms showing time to merge PRs and time to close issues.

    Args:
        df: Filtered interactions data for selected tools.
        global_df: Unfiltered interactions data for all tools. Defaults to None.
    """
    resolved_at = {"issue": "closed", "pr": "merged"}
    titles = {"pr": "Time to Merge Pull Requests", "issue": "Time to Close Issues"}
    labels = {"pr": "Days to Merge", "issue": "Days to Close"}

    st.subheader("Time to Resolution")
    st.markdown("""
    *Time to Resolution* refers to the duration taken to close or merge a PR or issue, measured from the time of creation to resolution.
    Shorter resolution times can indicate more efficient workflows and quicker feedback loops.
    They can also indicate a lack of engagement or thorough review, so should be interpreted in context.
    """)
    # Create two columns for side-by-side histograms
    col_resolve_1, col_resolve_2 = st.columns(2)
    cols = {"pr": col_resolve_1, "issue": col_resolve_2}
    for interaction, col in resolved_at.items():
        complete_time = get_complete_time(df, interaction, col)
        if complete_time.empty:
            cols[interaction].info("No resolution data available.")
            continue
        if global_df is not None:
            global_complete_time = get_complete_time(
                global_df, interaction, col
            ).median()
        else:
            global_complete_time = None
        fig = plot_histogram(
            complete_time,
            global_median=global_complete_time,
            title=titles[interaction],
            label=labels[interaction],
        )
        cols[interaction].plotly_chart(
            fig,
            width="stretch",
            config=FIG_CONFIG,
            key=f"{interaction}_resolution_histogram",
        )


def engagement_histograms(
    df: pd.DataFrame, global_df: pd.DataFrame | None = None
) -> None:
    """Create histograms showing engagement levels for PRs and issues.

    Displays distribution of comments, reactions, and reviews before resolution.

    Args:
        df: Filtered interactions data for selected tools.
        global_df: Unfiltered interactions data for all tools. Defaults to None.
    """
    titles = {"pr": "Pull Request Engagement", "issue": "Issue Engagement"}
    labels = {
        "pr": "Engagement (Comments/Reactions/Reviews)",
        "issue": "Engagement (Comments/Reactions)",
    }
    st.subheader("Engagement during Resolution")
    st.markdown("""
    *Engagement* refers to the number of comments, reactions, and reviews made on a PR or issue before it is closed or merged.
    Higher engagement can indicate more thorough reviews and feedback in PRs and active problem-solving and collaboration in Issues.
    """)
    _prs_with_reviews_caption(df)
    col_engagement_1, col_engagement_2 = st.columns(2)
    cols = {"pr": col_engagement_1, "issue": col_engagement_2}
    for interaction in cols.keys():
        engagement_time = _get_engagement(df, interaction)

        if engagement_time.empty:
            cols[interaction].info("No engagement data available.")
            continue

        if global_df is not None:
            global_engagement_time = _get_engagement(global_df, interaction).median()

        else:
            global_engagement_time = None
        fig = plot_histogram(
            engagement_time,
            global_median=global_engagement_time,
            title=titles[interaction],
            label=labels[interaction],
        )
        cols[interaction].plotly_chart(
            fig,
            width="stretch",
            config=FIG_CONFIG,
            key=f"{interaction}_engagement_histogram",
        )


def _prs_with_reviews_caption(df: pd.DataFrame) -> None:
    """Calculate and display percentage of PRs reviewed before merge."""
    df_pr = df.loc[(df.interaction == "pr")]
    cols = ["repo", "number"]
    is_reviewed = df_pr.loc[df_pr.subtype == "review", cols].drop_duplicates()
    is_closed = df_pr.loc[
        (df_pr.subtype == "author") & (df_pr.closed.notna() | df_pr.merged.notna()),
        cols,
    ].drop_duplicates()
    merged_and_reviewed = pd.merge(is_reviewed, is_closed, on=cols, how="inner")
    if not is_closed.empty:
        perc_prs_reviewed = len(merged_and_reviewed) / len(is_closed) * 100
        st.caption(
            f"{perc_prs_reviewed:.1f}% of PRs received at least one review before being merged/closed."
        )


def render_project_development_section(
    tool_url: str, tool_name: str, container: Any
) -> None:
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

    if filtered_df.empty:
        container.info("No development metrics available for this tool.")
        return

    # Calculate stats for header
    total_commits = len(filtered_df[filtered_df.interaction == "commit"])
    total_stars = len(filtered_df[filtered_df.interaction == "stargazer"])

    # Render glowy header
    header_template = _jinja_env.get_template("project_dev_header.html.jinja")
    header_html = header_template.render(
        html_url=tool_url,
        selected_tool=tool_name,
        total_commits=total_commits,
        total_stars=total_stars,
    )
    container.markdown(header_html, unsafe_allow_html=True)

    # Repository metrics over time
    container.markdown("### Repository Metrics Over Time")
    container.markdown(
        """
        These timelines visualise key development metrics for the selected repository over time.
        You can click on legend items to toggle visibility of specific metrics.
        """
    )

    # Get date range from data
    min_date = filtered_df[["merged", "created", "closed"]].min().min().date()
    max_date = filtered_df[["merged", "created", "closed"]].max().max().date()
    initial_min = (max_date - pd.DateOffset(years=1)).date()

    container.markdown("#### Filters")

    # Resolution control
    resolution = container.radio(
        "Resolution",
        options=["Daily", "Weekly", "Monthly"],
        index=1,
        key=f"time_resolution_{tool_name}",
        help="Select the time resolution for the timelines.",
        horizontal=True,
    )

    # Date range picker - use column to constrain width
    col_date = container.columns([1, 2])[0]
    date_range = col_date.date_input(
        "Select date range:",
        value=(max(min_date, initial_min), max_date),
        min_value=min_date,
        max_value=max_date,
        key=f"date_range_picker_{tool_name}",
        help="Filter interactions by date range. Click to open calendar picker.",
    )

    # Handle date range input (returns tuple when both dates selected)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        # Fallback if only one date selected
        start_date = end_date = (
            date_range if not isinstance(date_range, tuple) else date_range[0]
        )

    # Bot filter checkbox
    hide_bots = container.toggle(
        "Hide bot interactions",
        value=True,
        key=f"hide_bots_checkbox_{tool_name}",
        help="Filter out automated bot interactions (e.g., actions, codecov, pre-commit-ci).",
    )

    filtered_df = exclude_bot_interactions(filtered_df, hide_bots=hide_bots)

    # Cumulative toggle
    cumulative = container.toggle(
        "Toggle cumulative totals",
        value=True,
        key=f"cumulative_toggle_{tool_name}",
        help="When enabled, shows running totals accumulated over time. When disabled, shows counts for each time period.",
    )

    if filtered_df.empty:
        container.info("No data available for the selected date range.")
        return

    # Define color mapping
    colors = px.colors.sequential.Peach
    color_map = {
        metric: colors[idx % len(colors)] for idx, metric in enumerate(TOTALS_METRICS)
    }

    # Create cumulative metrics chart (pass FULL data, plotting function handles date range display)
    fig_cumulative = plot_totals_metrics(
        filtered_df,
        resolution=resolution,
        color_map=color_map,
        cumulative=cumulative,
        tool_name=tool_name,
    )
    container.plotly_chart(
        fig_cumulative, use_container_width=True, key=f"cumulative_metrics_{tool_name}"
    )

    # Create open metrics chart (pass FULL data, plotting function handles date range display)
    color_map_open = {
        metric: colors[idx % len(colors)] for idx, metric in enumerate(OPEN_METRICS)
    }
    fig_open = plot_open_metrics(
        filtered_df,
        resolution=resolution,
        color_map=color_map_open,
        tool_name=tool_name,
    )
    container.plotly_chart(
        fig_open,
        use_container_width=True,
        key=f"open_metrics_{tool_name}",
        config=FIG_CONFIG,
    )

    # Top contributors - apply date filter for this section
    container.markdown("### Top 10 Contributors")
    container.markdown("""
    Across all interaction types (issues, PRs, commits), these are the top 10 most active contributors for the selected tool and date range.

    Note that activity depends on contribution conventions and may not reflect overall impact.
    For instance, some repositories squash all commits made in a Pull Request into a single commit before merging it into the default project branch.
    This will result in fewer commits being recorded for contributors to those repositories.
    """)

    # Apply date filter to match original page behavior
    time_filtered_df = date_filter(filtered_df, (str(start_date), str(end_date)))

    top_users = (
        time_filtered_df.loc[
            time_filtered_df["interaction"].isin(["pr", "issue", "commit"]), "username"
        ]
        .value_counts()
        .head(10)
        .reset_index()
    )
    top_users.columns = ["username", "interaction_count"]

    cols = container.columns(5)
    for idx, row in top_users.iterrows():
        with cols[idx % 5]:
            avatar_url = f"https://github.com/{row['username']}.png?size=160"
            profile_url = f"https://github.com/{row['username']}"
            st.image(
                avatar_url,
                width=100,
                caption=f"[{row['username']}]({profile_url})\n\n{row['interaction_count']} interactions",
            )

    # Prepare global data for histogram comparison
    # Load all tools data with same filters (bot filtering + date filtering)
    global_df = exclude_bot_interactions(df, hide_bots=hide_bots)
    time_filtered_global_df = date_filter(global_df, (str(start_date), str(end_date)))

    user_classifications_df = load_user_classifications()
    detailed_org_contributions_breakdown(time_filtered_df, user_classifications_df)
    resolution_histograms(time_filtered_df, time_filtered_global_df)
    engagement_histograms(time_filtered_df, time_filtered_global_df)


# ============================================================================
# OSSF Security Scores
# ============================================================================


def score_to_gradient(score_str: str) -> str:
    """Converts a score string (e.g. '7') to a CSS style string with a color gradient."""
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


def build_tool_detail_table(
    tool_id: str, scores: pd.DataFrame, reasons: pd.DataFrame
) -> str:
    """Builds an HTML table showing detailed scores and reasons for a specific tool."""
    check_cols = [
        c for c in scores.columns if c not in ("html_url", "aggregated_score")
    ]

    reason_col_map = {
        col.removeprefix("Reason "): col
        for col in reasons.columns
        if col.startswith("Reason ")
    }

    score_row = scores.loc[tool_id]
    reason_row = reasons.loc[tool_id] if tool_id in reasons.index else None

    if isinstance(score_row, pd.DataFrame) or isinstance(reason_row, pd.DataFrame):
        raise ValueError(
            f"Duplicate rows found for tool_id '{tool_id}' in scores or reasons DataFrame. "
            "Each tool must appear only once."
        )
    SCORECARD_DOCS_BASE = "https://github.com/ossf/scorecard/blob/main/docs/checks.md#"

    rows = []
    for check in check_cols:
        raw_score = score_row.get(check, "?")
        try:
            val = float(raw_score)
            if val < 0 or pd.isna(val):
                display_val = "None"
            else:
                display_val = str(int(val)).strip()
        except (ValueError, TypeError):
            display_val = "None"

        cell_style = score_to_gradient(display_val)

        reason_col = reason_col_map.get(check)
        if reason_col and reason_row is not None:
            reason_text = reason_row.get(reason_col, "No reason available")
            # Also skip if reason is NaN
            try:
                if pd.isna(reason_text):
                    continue
            except (TypeError, ValueError):
                pass
        else:
            reason_text = "No reason available"
        if not reason_text.endswith("."):
            reason_text = reason_text + "."

        # Build docs anchor: lowercase, spaces → hyphens
        doc_url = f"{SCORECARD_DOCS_BASE}{check.casefold()}"

        rows.append(
            {
                "cell_style": cell_style,
                "display_val": display_val,
                "doc_url": doc_url,
                "check": check,
                "reason_text": reason_text,
            }
        )

    template = _jinja_env.get_template("ossf_detail_table.html.jinja")
    return template.render(rows=rows)


def render_ossf_section(tool_url: str, tool_name: str, container: Any) -> None:
    """Render OSSF security scores."""
    # Add explanatory text
    container.markdown(
        """
        The dashboard provides a detailed view of the [OpenSSF Scorecard](https://github.com/ossf/scorecard?tab=readme-ov-file#what-is-scorecard) results for each tool in our inventory.
        Select a tool from the dropdown to see its overall score and a breakdown of individual checks along with
        the reasons for any failed or low-scoring checks. The scores are colour-coded to help you quickly identify
        areas of strength and weakness in the security posture of each tool. The scores shown below are
        on a scale from **0 to 10**, where **10** represents the highest level of security compliance.
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
    html_url = score_row.get("html_url", "#")

    header_template = _jinja_env.get_template("ossf_tool_header.html.jinja")
    header_html = header_template.render(
        html_url=html_url, selected_tool=tool_name, agg_style=agg_style, agg=agg
    )
    container.markdown(header_html, unsafe_allow_html=True)

    html_content = build_tool_detail_table(tool_id, scores, reasons)
    components.html(html_content, height=800, scrolling=True)


# ============================================================================
# Download Trends
# ============================================================================


def render_downloads_section(tool_url: str, tool_name: str, container: Any) -> None:
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
    container.plotly_chart(fig, use_container_width=True)


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

    # Render glowy page header
    header_template = _jinja_env.get_template("tool_deep_dive_header.html.jinja")
    header_html = header_template.render(html_url=tool_url, selected_tool=tool_name)
    st.markdown(header_html, unsafe_allow_html=True)
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
