# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Create Streamlit web app sub-page to visualise project development metrics."""

import textwrap
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

FIG_CONFIG = {"displayModeBar": False, "doubleClick": False, "scrollZoom": False}
RESOLUTION_CONVERTER = {"Daily": "D", "Weekly": "W", "Monthly": "ME"}

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


@st.cache_data
def map_repo_to_tool(user_stats_df: pd.DataFrame, repo_col: str) -> list[dict]:
    """Map repository names to tool names.

    Args:
        user_stats_df (pd.DataFrame): User stats dataframe.
        repo_col (str): Name of the column containing repository names.

    Returns:
        list[dict]: List of dictionaries mapping repository names to tool names.
    """
    available_repos = set(
        (",".join(user_stats_df[repo_col].str.lower().values)).split(",")
    )
    tools_df = pd.read_csv(
        Path(__file__).parent.parent.parent / "inventory" / "output" / "filtered.csv"
    )
    urls = {repo: "https://github.com/" + repo.lower() for repo in available_repos}
    repo_to_tool_map = [
        {
            "repo": repo,
            "name": tools_df.loc[tools_df.url == urls[repo], "name"]
            .item()
            .split(",")[0],
        }
        for repo, url in urls.items()
        if url in tools_df.url.values
    ]
    return repo_to_tool_map


@st.cache_data
def create_vis_table(filepath: Path) -> pd.DataFrame:
    """Load and prepare user interactions data.

    Args:
        filepath: Path to user interactions data file.

    Returns:
        DataFrame containing user interactions with parsed datetime columns.
    """
    # Check if user analysis data exists
    df = pd.read_csv(filepath, parse_dates=["created", "closed", "merged"]).dropna(
        subset=["username", "repo"], how="any"
    )
    st.session_state["interaction_df"] = df

    return df


def filter_interactions(
    df: pd.DataFrame,
    repo_to_tool_map: list[dict],
    selected_tools: list[str] | None,
    hide_bots: bool = True,
) -> pd.DataFrame:
    """Filter interactions by tools, bots, and date range.

    Args:
        df: DataFrame containing user interaction data.
        repo_to_tool_map: List of dictionaries mapping repository names to tool names.
        selected_tools: List of tool names to filter, or None for all tools.
        hide_bots: Whether to filter out bot interactions. Defaults to True.

    Returns:
        Filtered DataFrame containing interactions matching the criteria.
    """
    bot_patterns = [
        "-bot",
        "actions",
        "dependabot",
        "JuliaTagBot",
        "pudlbot",
        "codebot",
        "renovate",
        "sonarqubecloud",
        "codecov",
        "coveralls",
        "pre-commit-ci",
    ]
    if hide_bots:
        mask = ~df["username"].str.contains(
            "|".join(bot_patterns), case=False, na=False
        )
        df = df[mask]

    # Filter interactions by selected tools
    if selected_tools:
        selected_repos = [
            item["repo"] for item in repo_to_tool_map if item["name"] in selected_tools
        ]
        df = df[df.repo.str.contains("|".join(selected_repos), case=False)]
    return df


def date_filter(df: pd.DataFrame, date_range: tuple[str, str]) -> pd.DataFrame:
    """Filter DataFrame by date range.

    Args:
        df (pd.DataFrame): DataFrame to filter.
        date_range (tuple[str, str]): Start and end dates (YYYY-MM-DD) for filtering.

    Returns:
        pd.DataFrame: Filtered DataFrame.
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
    plot_type: Literal["bar", "line"] = "bar",
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
    df: pd.DataFrame, resolution: str, color_map: dict, cumulative: bool = True
) -> go.Figure:
    """Create cumulative metrics timeline chart.

    Args:
        df: DataFrame containing interaction data.
        resolution: Time resolution for resampling ('Daily', 'Weekly', or 'Monthly').
        color_map: Dictionary mapping metric names to colors.
        cumulative: Whether to show cumulative counts. Defaults to True.

    Returns:
        Plotly Figure showing cumulative repository metrics over time.
    """
    resample = f"1{RESOLUTION_CONVERTER[resolution]}"
    totals_df = get_totals(
        df[df.subtype.isnull() | (df.subtype == "author")], "created", resample
    )
    if cumulative:
        totals_df = totals_df.cumsum()
    plot_df = (
        totals_df.stack()
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


def plot_open_metrics(df: pd.DataFrame, resolution: str, color_map: dict) -> go.Figure:
    """Create open issues and PRs timeline chart.

    Args:
        df: DataFrame containing interaction data.
        resolution: Time resolution for resampling ('Daily', 'Weekly', or 'Monthly').
        color_map: Dictionary mapping metric names to colors.

    Returns:
        Plotly Figure showing open issues and PRs over time.
    """
    resample = f"1{RESOLUTION_CONVERTER[resolution]}"
    _df = df.loc[df["interaction"].isin(["issue", "pr"]) & (df["subtype"] == "author")]
    _df.loc[:, "closed"] = _df["closed"].fillna(_df["merged"])
    created_df = get_totals(_df, "created", resample).cumsum()
    closed_df = get_totals(_df, "closed", resample).cumsum()
    closed_df_full = closed_df.reindex(created_df.index).ffill().fillna(0)
    open_df = created_df.subtract(closed_df_full).rename(
        columns=lambda x: x.replace("Total ", "Open ")
    )
    assert (open_df >= 0).all().all(), "Open counts contain negative values!"
    extra_dfs = []
    for subtype in ["comment", "review"]:
        _df = get_totals(
            df.loc[
                df["interaction"].isin(["issue", "pr"]) & (df["subtype"] == subtype)
            ],
            "created",
            resample,
        ).rename(
            columns=lambda x: x.replace("Total ", "New ").removesuffix("s")
            + f" {subtype.title()}s"
        )
        extra_dfs.append(_df)

    plot_df = (
        pd.concat([open_df, *extra_dfs], axis=1)
        .stack()
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


def daily_interactions_timeline(df: pd.DataFrame):
    """Create interactive timeline visualisation of repository metrics.

    Displays cumulative metrics (stars, forks, commits, closed issues, merged PRs) and
    open counts (issues, PRs) over time with configurable resolution and metric selection.

    Args:
        df: DataFrame containing interaction data.
    """
    st.subheader("Repository Metrics Over Time")

    st.markdown("""
    These timelines visualise key development metrics for the selected repositories over time.
    On changing the date range, cumulative metrics reset to zero at the start of the selected period.
    """)
    # Metric options split into two groups
    col1, col2, _ = st.columns([1, 1, 2])
    resolution = col1.radio(
        "Resolution",
        options=["Daily", "Weekly", "Monthly"],
        index=1,
        key="time_resolution_filter",
        help="Select the time resolution for the timelines.",
        horizontal=True,
    )

    cumulative = col2.toggle(
        "Toggle cumulative totals", value=True, key="cumulative_toggle"
    )

    # Define color mapping for all metrics

    colors = px.colors.sequential.Peach
    color_map = {
        metric: colors[idx % len(colors)] for idx, metric in enumerate(TOTALS_METRICS)
    }
    # Create cumulative metrics chart
    fig_cumulative = plot_totals_metrics(
        df, resolution=resolution, color_map=color_map, cumulative=cumulative
    )
    st.plotly_chart(
        fig_cumulative,
        width="stretch",
        key="cumulative_metrics_plot",
        config=FIG_CONFIG,
    )

    color_map = {
        metric: colors[idx % len(colors)] for idx, metric in enumerate(OPEN_METRICS)
    }
    # Create open counts chart
    fig_open = plot_open_metrics(df, resolution=resolution, color_map=color_map)
    st.plotly_chart(
        fig_open, width="stretch", key="open_metrics_plot", config=FIG_CONFIG
    )


def top_users_display(df: pd.DataFrame):
    """Display top 10 contributors with GitHub avatars.

    Args:
        df: DataFrame containing interaction data.
    """
    # Get top 10 users from the already filtered data
    st.subheader("Top 10 Contributors")
    st.markdown("""
    Across all interaction types (issues, PRs, commits), these are the top 10 most active contributors for the selected tools and date range.

    Note that activity depends on contribution conventions and may not reflect overall impact.
    For instance, some repositories squash all commits made in a Pull Request into a single commit before merging it into the default project branch.
    This will result in fewer commits being recorded for contributors to those repositories.
    """)
    top_users = (
        df.loc[df["interaction"].isin(["pr", "issue", "commit"]), "username"]
        .value_counts()
        .head(10)
        .reset_index()
    )
    top_users.columns = ["username", "interaction_count"]
    # Display top users with GitHub avatars
    cols = st.columns(5)
    for idx, row in top_users.iterrows():
        col_idx = idx % 5
        with cols[col_idx]:
            # GitHub avatar URL
            avatar_url = f"https://github.com/{row['username']}.png?size=160"
            profile_url = f"https://github.com/{row['username']}"
            st.image(
                avatar_url,
                width=100,
                caption=textwrap.dedent(f"""\
                [{row["username"]}]({profile_url})

                {row["interaction_count"]} interactions"""),
            )


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


def resolution_histograms(df: pd.DataFrame, global_df: pd.DataFrame | None = None):
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


def engagement_histograms(df: pd.DataFrame, global_df: pd.DataFrame | None = None):
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

    def __reviewed_before_merge(df: pd.DataFrame) -> bool | float:
        is_merged = df[
            (df.subtype == "author") & (df.closed.notna() | df.merged.notna())
        ]
        reviews = df[df.subtype == "review"]
        if is_merged.empty:
            return float("nan")
        return False if reviews.empty else True

    pr_interactions = df.loc[(df.interaction == "pr")]
    merged_and_reviewed = pr_interactions.groupby(["repo", "number"]).apply(
        __reviewed_before_merge, include_groups=False
    )
    if not merged_and_reviewed.isna().all():
        perc_prs_reviewed = (
            merged_and_reviewed.sum() / len(merged_and_reviewed.dropna()) * 100
        )
        st.caption(
            f"{perc_prs_reviewed:.1f}% of PRs received at least one review before being merged/closed."
        )


def preamble():
    """Text to show before the user data plots."""
    st.markdown(
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

        Use the filters on the left to change the time period of these interactions, select specific tools to analyse, and filter out known "bot" activity (interactions from automated accounts).
        """
    )


def main(df_vis: pd.DataFrame):
    """Main function for the Project Development Metrics page."""
    repo_to_tool_map = map_repo_to_tool(df_vis, "repo")

    # Sidebar filters
    all_tools_toggle = st.sidebar.toggle(
        "Show analysis for all tools",
        value=True,
        help="Toggle to view analysis for all tools or select specific tools below.",
    )
    selected_tools = st.sidebar.multiselect(
        "Select repositories to analyse in aggregate",
        options=sorted(np.unique([i["name"] for i in repo_to_tool_map])),
        disabled=all_tools_toggle,
        help="Choose one or more specific tools to analyse. Disabled when 'Show analysis for all tools' is enabled.",
    )
    if not selected_tools and not all_tools_toggle:
        st.warning("Please select at least one tool to analyse.")
        return

    # Bot filter
    hide_bots = st.sidebar.checkbox(
        "Hide bot interactions",
        value=True,
        key="hide_bots_checkbox",
        help="Filter out automated bot interactions (e.g., actions, codecov, pre-commit-ci).",
    )

    # Apply all filters including date range
    filtered_interactions = filter_interactions(
        df_vis,
        repo_to_tool_map,
        selected_tools if not all_tools_toggle else None,
        hide_bots=hide_bots,
    )
    # Pass filtered data to visualisation functions
    if filtered_interactions.empty:
        st.warning("No interaction data available for the selected filters.")
        return

    # Get date range from the data
    min_date = filtered_interactions[["merged", "created", "closed"]].min().min().date()
    max_date = filtered_interactions[["merged", "created", "closed"]].max().max().date()

    default_range = (min_date, max_date)
    initial_min = (max_date - pd.DateOffset(years=1)).date()
    current_range = st.session_state.get(
        "selected_date_range_dev", (max(min_date, initial_min), max_date)
    )
    # Date range selector
    start_date, end_date = st.sidebar.slider(
        "Select date range:",
        min_value=min_date,
        max_value=max_date,
        value=current_range,
        key="date_range_slider_dev",
        label_visibility="visible",
        help="Filter interactions by date range. Adjust the slider to focus on a specific time period.",
    )

    if default_range != (start_date, end_date):
        # Update filtered interactions based on date range
        filtered_interactions = date_filter(
            filtered_interactions, (str(start_date), str(end_date))
        )
    # Pass filtered data to visualisation functions
    if filtered_interactions.empty:
        st.warning("No interaction data available for the selected filters.")
        return

    if not all_tools_toggle and selected_tools:
        # Only pass global data if specific tools are selected
        global_interactions = filter_interactions(
            df_vis,
            repo_to_tool_map,
            None,  # No tool filter for global data
            hide_bots=hide_bots,
        )
        if default_range != current_range:
            # Update filtered interactions based on date range
            global_interactions = date_filter(
                global_interactions, (str(start_date), str(end_date))
            )

    else:
        global_interactions = None

    daily_interactions_timeline(filtered_interactions)
    top_users_display(filtered_interactions)
    resolution_histograms(filtered_interactions, global_interactions)
    engagement_histograms(filtered_interactions, global_interactions)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Project Development Metrics", page_icon="📊", layout="wide"
    )

    st.title("Project Development Metrics")

    user_stats_dir = Path(__file__).parent.parent.parent / "user_analysis" / "output"
    # We're sharing this cached data with the main page, but we have to account for it being loaded for the first time here.
    df_vis = st.session_state.get(
        "df_interactions", create_vis_table(user_stats_dir / "user_interactions.csv")
    )

    preamble()
    main(df_vis)
