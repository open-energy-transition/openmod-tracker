# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Create Streamlit web app to visualise tool inventory data."""

import datetime
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Literal

import git
import markdown
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import util
from bs4 import BeautifulSoup
from st_keyup import st_keyup

OET_LOGO_FULL_NAME = "https://raw.githubusercontent.com/open-energy-transition/handbook/a8c0a9d55a543093008c7b58e7ed9efa6d9d633f/static/img/oet_standard_red_svg.svg"
OET_LOGO_ABBREVIATED = "https://raw.githubusercontent.com/open-energy-transition/handbook/a8c0a9d55a543093008c7b58e7ed9efa6d9d633f/static/img/oet_standard_red_png.png"

COLUMN_NAME_MAPPING: dict[str, str] = {
    "created_at": "Created",
    "updated_at": "Updated",
    "stargazers_count": "Stars",
    "commit_stats.total_committers": "Contributors",
    "commit_stats.dds": "DDS",
    "forks_count": "Forks",
    "dependent_repos_count": "Dependents",
    "last_month_downloads": "1 Month Downloads",
    "category": "Category",
    "language": "Language",
}

COLUMN_DTYPES: dict[str, Callable] = {
    "created_at": pd.to_datetime,
    "updated_at": pd.to_datetime,
    "stargazers_count": pd.to_numeric,
    "commit_stats.total_committers": pd.to_numeric,
    "commit_stats.dds": lambda x: 100 * pd.to_numeric(x),
    "forks_count": pd.to_numeric,
    "dependent_repos_count": pd.to_numeric,
    "last_month_downloads": pd.to_numeric,
    "category": lambda x: x.str.split(","),
}

NUMBER_FORMAT: dict[str, str] = {
    "Stars": "localized",
    "Contributors": "localized",
    "DDS": "%d%%",
    "Forks": "localized",
    "Dependents": "localized",
    "1 Month Downloads": "localized",
}

COLUMN_HELP: dict[str, str] = {
    "Created": "First ever repository commit",
    "Updated": "Most recent repository commit",
    "Stars": "Repository bookmarks",
    "Contributors": "All-time source code contributors",
    "DDS": "Development distribution score (the bigger the number the better, 0 means only one contributor. [Click for more info](https://report.opensustain.tech/chapters/development-distribution-score))",
    "Forks": "Number of Git forks",
    "Dependents": "Packages dependent on this project (only available if the project is indexed on a package repository)",
    "1 Month Downloads": "Package installs last month (only available if the project is indexed on a package repository)",
    "Category": "Category of energy system planning / operation problem for which this tool could be used. This is based on [G-PST entries](https://api.github.com/repos/G-PST/opentools) and our own manual assignment applied to a subset of tools.",
    "Docs": "Link to tool documentation.",
    "Score": "The tool score is a weighted average of all numeric metrics, after scaling those metrics to similar ranges.",
    "Interactions": "The cumulative sum of interactions with the repository in the past 6 months at a weekly resolution. Interactions include new stars, issues, forks, and pull requests. Data only available for GitHub-hosted repositories.",
    "Language": "The programming language in which the majority of the tool source code is written.",
}

EXTRA_COLUMNS = ["name_with_url", "Docs", "Score", "Interactions"]
DEFAULT_ORDER = "Stars"
NOT_OPEN_SOURCE_LANGUAGES = ["gams", "matlab", "jetbrains mps", "powerbuilder", "ampl"]


@st.cache_data
def create_vis_table(tool_stats_dir: Path, user_stats_dir: Path) -> pd.DataFrame:
    """Create the tool table with columns renamed and filtered ready for visualisation.

    Args:
        tool_stats_dir (Path): The directory in which to find tool list and stats.
        user_stats_dir (Path): The directory in which to find tool user stats.

    Returns:
        pd.DataFrame: Filtered and column renamed tool table.
    """
    stats_df = pd.read_csv(tool_stats_dir / "stats.csv", index_col="id")
    tools_df = pd.read_csv(tool_stats_dir / "filtered.csv", index_col="id")
    docs_df = pd.read_csv(tool_stats_dir / "docs.csv", index_col="id")

    df = pd.merge(left=stats_df, right=tools_df, right_index=True, left_index=True)
    df["Interactions"] = (
        _create_user_interactions_timeseries(user_stats_dir)
        .reindex(df.url.values)
        .values
    )

    # Assume: projects categorised as "Jupyter Notebook" are actually Python projects.
    # This occurs because the repository language is based on number of lines and Jupyter Notebooks have _a lot_ of lines.
    df["language"] = (
        df.language.replace({"Jupyter Notebook": "Python"}).str.lower().astype("string")
    )

    # Add the tool name to the end of the URL after a `#`.
    # This allows us to use regex to show the tool name in a streamlit "link column" while still making the URL valid to direct users to the source code.
    df["name_with_url"] = df.url + "#" + df.name.apply(lambda x: x.split(",")[0])

    for col, dtype_func in COLUMN_DTYPES.items():
        df[col] = dtype_func(df[col])
    df["Docs"] = (
        docs_df["pages"]
        .fillna(docs_df["rtd"])
        .fillna(docs_df["wiki"])
        .fillna(df["homepage"])
    )
    df["Score"] = pd.Series(
        np.random.choice([0, 100], size=len(df.index)), index=df.index
    )
    df_vis = df.rename(columns=COLUMN_NAME_MAPPING)[
        EXTRA_COLUMNS + list(COLUMN_NAME_MAPPING.values())
    ]

    return df_vis


def _create_user_interactions_timeseries(
    tool_data_dir: Path, resolution: str = "7d", n_months: int = 6
) -> pd.Series:
    """Create a cumulative sum timeseries of github repo user interactions.

    Args:
        tool_data_dir (Path): The directory in which to find user interaction data.
        resolution (str, optional): Resolution of timeseries to resample data. Defaults to 7d (weekly).
        n_months (int, optional): Number of months prior to today of data to keep.

    Returns:
        pd.Series:
            Streamlit table bar plot compatible data stored in a pandas Series.
            This is not a data structure that pandas really supports as the dtype is list-like.
    """
    user_df = pd.read_csv(
        tool_data_dir / "user_interactions.csv", parse_dates=["created"]
    )
    interactions = (
        user_df.groupby([user_df.created, user_df.repo])
        .count()["interaction"]
        .unstack("repo")
        .resample(resolution)
        .sum()
        .T
    )
    last_6me_interactions = interactions.loc[
        :,
        interactions.columns.tz_localize(None).to_pydatetime()
        > (pd.to_datetime("now") - pd.DateOffset(months=n_months)),
    ].cumsum(axis=1)

    map_repo = {
        idx: "https://github.com/" + idx.lower() for idx in last_6me_interactions.index
    }
    last_6me_interactions.index = last_6me_interactions.index.map(map_repo)

    streamlit_ready_interactions = last_6me_interactions.groupby(
        last_6me_interactions.index
    ).apply(lambda x: x.values[0])

    return streamlit_ready_interactions


def numeric_range_filter(
    col: pd.Series, min_val: float | int, max_val: float | int
) -> pd.Series:
    """Filter numeric column.

    Args:
        col (pd.Series): Column to filter.
        min_val (float | int): Lower bound (inclusive).
        max_val (float | int): Upper bound (inclusive).

    Returns:
        pd.Series: Filtered `col`.
    """
    return ((col >= min_val) & (col <= max_val)) | col.isna()


def date_range_filter(
    col: pd.Series, start_date: datetime.date, end_date: datetime.date
) -> pd.Series:
    """Filter datetime column.

    Will only filter to dates, not to hours or other high frequencies.

    Args:
        col (pd.Series): Column to filter.
        start_date (datetime.date): Lower datetime bound (inclusive).
        end_date (datetime.date): Upper datetime bound (inclusive).

    Returns:
        pd.Series: Filtered `col`.
    """
    start_datetime = pd.Timestamp(start_date)
    end_datetime = pd.Timestamp(end_date) + pd.Timedelta(hours=23, minutes=59)
    col_no_tz = col.dt.tz_localize(None)
    return ((col_no_tz >= start_datetime) & (col_no_tz <= end_datetime)) | col.isna()


def categorical_filter(col: pd.Series, to_filter: Iterable) -> pd.Series:
    """Filter string columns.

    Args:
        col (pd.Series): Column to filter.
        to_filter (Iterable): List of category items to keep.

    Returns:
        pd.Series: Filtered `col`.
    """
    return col.isin(to_filter) | col.isna()


def list_filter(col: pd.Series, to_filter: Iterable) -> pd.Series:
    """Filter list columns.

    Dataframes shouldn't really be holding lists so this is a bit of a hack.

    Args:
        col (pd.Series): Column to filter.
        to_filter (Iterable): List of category items to keep.

    Returns:
        pd.Series: Filtered `col`.
    """
    with pd.option_context("future.no_silent_downcasting", True):
        return (
            col.dropna()
            .apply(lambda x: any(i in x for i in to_filter))
            .reindex(col.index)
            .fillna(True)
            .infer_objects()
        )


def add_scoring(cols: list[str]) -> float:
    """Create inputs for defining the score weighting for a given column and the metric scaling method.

    Args:
        cols (list[str]): List
        score_col (st.container): Streamlit column in which to add the number input.

    Returns:
        float: Column score weighting
    """
    st.toggle(
        "Add score column to table",
        value=util.get_state("score_toggle", False),
        key="score_toggle",
    )
    selectbox_cols = st.columns(len(cols))
    selectbox_cols[0].selectbox(
        "Metric scaling method",
        ("rank", "min-max"),
        help="""Select the method by which metrics should be scaled to bring them to a similar range.
        `rank` uses the absolute rank of a tool for each metric.
        `min-max` uses [min-max normalisation](https://en.wikipedia.org/wiki/Feature_scaling#Rescaling_(min-max_normalization)).
        """,
        key="scoring_method",
    )
    score_cols = st.columns(len(cols))
    for i, score_col in enumerate(score_cols):
        col_name = cols[i]
        number = score_col.number_input(
            label=col_name,
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.1,
            format="%0.01f",
            key=f"scoring_{col_name}",
        )

    return number


def update_score_col(df: pd.DataFrame) -> pd.Series:
    """Generate a new set of scores by combining all columns of the given dataframe.

    Args:
        df (pd.DataFrame): Tool metric table containing only columns relevant to scoring.

    Returns:
        pd.Series: Tool score.
    """
    # Add tool score by combining metrics with the provided weightings
    scores = {col: util.get_state(f"scoring_{col}", 0.5) for col in df.columns}
    scoring_method = util.get_state("scoring_method", "rank")
    normalised_data = normalise(df, scoring_method)
    score = normalised_data.mul(scores).div(sum(scores.values())).sum(axis=1).mul(100)
    return score


def normalise(
    df: pd.DataFrame, scaling_method: Literal["min-max", "rank"]
) -> pd.DataFrame:
    """Scale each column of the given dataframe relative to data in that column.

    Args:
        df (pd.DataFrame): Tool metric table. All columns must be numeric.
        scaling_method (Literal[min-max, rank]): Tool scaling method to use

    Returns:
        pd.DataFrame: `df` with each column scaled.
    """
    if scaling_method == "min-max":
        return (df - df.min()) / (df.max() - df.min())
    elif scaling_method == "rank":
        return df.rank() / df.rank().max()


def slider(
    col: pd.Series, reset_mode: bool, plot_dist: bool = True
) -> tuple[float, float] | tuple[datetime.date, datetime.date]:
    """Generate a slider for numeric / datetime table data.

    Args:
        col (pd.Series): Data table column.
        reset_mode (bool): Whether to reset slider to initial values.
        plot_dist (bool): If True, add a distribution plot of the column's data above the slider.

    Returns:
        tuple[float, float] | tuple[datetime.date, datetime.date]:
            Min/max values given by slider to use in data table filtering.
            Will be in datetime format if that was the format of the inputs, otherwise floats.
    """
    state_name = f"slider_{col.name}"
    if col.dtype.kind == "M":
        default_range = (col.min().date(), col.max().date())
    else:
        default_range = (col.min(), col.max())
    current_range = (
        default_range if reset_mode else util.get_state(state_name, default_range)
    )
    if col.dtype.kind == "M":
        slider_range = tuple(pd.Timestamp(i).timestamp() for i in current_range)
        col = col.apply(lambda x: x.timestamp())
    else:
        slider_range = current_range

    if plot_dist:
        dist_plot(col, slider_range)

    selected_range = st.sidebar.slider(
        f"Range for {col.name}",
        min_value=default_range[0],
        max_value=default_range[1],
        value=current_range,
        key=state_name,
    )
    if selected_range != default_range:
        util.get_state("filters")["slider"].append(col.name)

    return selected_range


def multiselect(unique_values: list[str], col: str, reset_mode: bool) -> list[str]:
    """Generate a multiselect box for categorical table data.

    Args:
        unique_values (list[str]): Unique categorical values.
        col (str): Column name.
        reset_mode (bool): Whether to reset multiselect to initial values.

    Returns:
        list[str]: values given by multiselect to use in data table filtering.

    Note:
        - The `Language` column has a custom toggle that we need to account for in creating its multiselect box.
          We handle that directly in this method.
    """
    state_name = f"multiselect_{col}"
    current_selected = (
        unique_values if reset_mode else util.get_state(state_name, unique_values)
    )

    if col.lower() == "language":
        exclude_proprietary = proprietary_language_toggle(reset_mode)
        if exclude_proprietary:
            current_selected = sorted(
                set(current_selected).difference(NOT_OPEN_SOURCE_LANGUAGES)
            )
        else:
            current_selected = sorted(
                set(current_selected)
                | util.get_state("selected_proprietary").intersection(unique_values)
            )

    selected_values = st.sidebar.multiselect(
        f"Select {col} values",
        options=unique_values,
        default=current_selected,
        key=state_name,
    )

    if col.lower() == "language" and not util.get_state("exclude_proprietary"):
        util.set_state(
            "selected_proprietary",
            set(selected_values).intersection(NOT_OPEN_SOURCE_LANGUAGES),
        )

    if selected_values != unique_values:
        util.get_state("filters")["multiselect"].append(col)
    return selected_values


def reset(button_press: bool = False) -> bool:
    """Return result of the reset button having been pressed.

    Args:
        button_press (bool, optional): If pressed, this will be True. Defaults to False.

    Returns:
        bool: True if it is time to reset, False otherwise.
    """
    # Reset filters button and logic
    if button_press:
        # Set a flag to indicate we want to reset
        util.set_state("reset_filters", True)
        st.rerun()

    # Check if we need to reset filters
    reset_mode = util.get_state("reset_filters", False)
    if reset_mode:
        # Clear the reset flag
        util.set_state("reset_filters", False)
    return reset_mode


def header_and_missing_value_toggle(col: pd.Series, reset_mode: bool) -> bool:
    """Create sidebar subheader and missing value toggle for a column.

    Args:
        col (pd.Series): Stats table column.
        reset_mode (bool): Whether to reset multiselect to initial values.

    Returns:
        bool: True if there are NaN values and the missing value toggle is switched on.
    """
    name: str = col.name  # type:ignore
    st.sidebar.subheader(name, help=COLUMN_HELP[name])
    missing_count = col.isnull().sum()
    state_name = f"exclude_nan_{name}"
    if missing_count > 0:
        exclude_nan = st.sidebar.toggle(
            f"Exclude {missing_count} tools missing `{name}` data",
            value=False if reset_mode else util.get_state(state_name, False),
            key=state_name,
        )
        if exclude_nan:
            util.get_state("filters")["toggle"].append(name)
    else:
        exclude_nan = False
    return exclude_nan


def proprietary_language_toggle(reset_mode: bool) -> bool:
    """Create toggle to add / remove tools using proprietary languages.

    Args:
        reset_mode (bool): Whether to reset multiselect to initial values.

    Returns:
        bool: True if there are NaN values and the missing value toggle is switched on.
    """
    exclude_proprietary = st.sidebar.toggle(
        "Exclude tools which can only run with access to proprietary software",
        value=True if reset_mode else util.get_state("exclude_proprietary", True),
        key="exclude_proprietary",
    )
    util.init_state("selected_proprietary", set(NOT_OPEN_SOURCE_LANGUAGES))
    return exclude_proprietary


@st.cache_data
def _distribution_table(col: pd.Series, bins: int = 30) -> pd.DataFrame:
    """Pre-compute histogram representing the distribution of values for each numeric column of the tool stats table.

    This reduces the calculation complexity on re-running the streamlit app.

    Args:
        col (pd.Series): Numeric column of the tool stats table.
        bins (int): Number of histogram bins to use in generating the tables. Defaults to 30.

    Returns:
        pd.DataFrame: x/y values of histogram describing the distribution of values in `col`.
    """
    y, x = np.histogram(col.dropna(), bins=bins)
    # bin edges to midpoint
    x = [(a + b) / 2 for a, b in zip(x, x[1:])]

    return pd.DataFrame({"x": x, "y": y})


def _plotly_plot(df: pd.DataFrame) -> go.Figure:
    """Create a static plotly bar plot.

    The fill colour of bars is dictated by the "color" column, with "in"/"out" values in the column coloured as red/grey, respectively.
    The resulting figure will have no interactivity.
    These plots are meant to be updated by user-induced changes that are passed by streamlit in the form of changes to the dataframe.

    Args:
        df (pd.DataFrame): Data to plot, with "x", "y", and "color" columns

    Returns:
        go.Figure: Plotly figure.
    """
    fig = px.bar(
        df,
        x="x",
        y="y",
        color="color",
        color_discrete_map={"in": "#FF4B4B", "out": "#A3A8B8"},
    )
    fig.update_layout(
        yaxis_title=None,
        yaxis={"visible": False, "range": (0, df.y.max())},
        xaxis={"visible": False},
        margin={"b": 0, "t": 0},
        bargap=0,
        showlegend=False,
        height=100,
        title="",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_traces(hoverinfo="skip", hovertemplate=None)
    return fig


def dist_plot(col: pd.Series, slider_range: tuple[float, float]) -> None:
    """Create a distribution plot in the sidebar.

    Args:
        col (pd.Series): Column of data linked to the distribution data table.
        slider_range (tuple[float, float]): Min/max defined by the user-defined slider values.
    """
    df_dist = _distribution_table(col)
    df_dist["color"] = [
        "in" if ((i >= slider_range[0]) & (i <= slider_range[1])) else "out"
        for i in df_dist.x
    ]
    fig = _plotly_plot(df_dist)

    config = {"displayModeBar": False, "staticPlot": True}
    st.sidebar.plotly_chart(
        fig,
        selection_mode=[],
        use_container_width=True,
        key=f"{col.name}_chart",
        config=config,
    )


def create_filter_message() -> str:
    """Create a message listing all the columns on which a filter has been applied by the user."""
    filters = util.get_state("filters")
    messages = []
    if filters["multiselect"] or filters["slider"]:
        to_filter = [
            f"`{name}`"
            for name in sorted(set(filters["multiselect"] + filters["slider"]))
        ]
        messages.append(f"filtered on subset of: {', '.join(to_filter)}")
    if filters["toggle"]:
        to_filter = [f"`{name}`" for name in sorted(set(filters["toggle"]))]
        messages.append(f"excluding missing data in: {', '.join(to_filter)}")
    if messages:
        message = " (" + "; ".join(messages) + ")"
    else:
        message = ""
    return message


def extract_processing_approach_from_readme(readme: Path, header: str) -> str:
    """Extract all HTML text from the README below a given (sub)header.

    Args:
        readme (Path): Path to the repository README.
        header (str): header to extract the text from under.

    Returns:
        str: HTML string of content under the header. Does not include the header string itself.
    """
    text = markdown.markdown(readme.read_text())
    soup = BeautifulSoup(text, "html.parser")
    h3 = soup.find("h3", string=header)
    all_html = ""
    for sib in h3.find_next_siblings():
        if sib.name in ["h1", "h2", "h3"]:
            break
        else:
            all_html += str(sib)
    return all_html


def preamble(latest_changes: str, n_tools: int, data_processing_text: str):
    """Text to show before the app table.

    Args:
        latest_changes (str): the date associated with the most recent changes to the table.
        n_tools (int): Number of tools shown in the table.
        data_processing_text (str): HTML text snippet to drop into the data processing explainer box.
    """
    st.markdown(
        """
        # Open Energy Modelling Tool Tracker
        """
    )

    # Custom styles to make the beta expander more prominent
    st.html(
        """
        <style>
            div.st-key-beta-expander [data-testid=stExpander] details summary{
                background-color: rgba(255, 165, 0, 0.3);
            }
            div.st-key-beta-expander [data-testid=stExpander] details summary p{
                font-size: 1rem;
            }
        </style>
        """
    )
    with st.container(key="beta-expander"):
        with st.expander("We're still in beta", icon="🚧"):
            st.markdown(
                """
                This dashboard is still a work in progress.
                We are continuously working to improve the user experience and add new features.

                Features we have in the pipeline include:

                - a tool feature matrix to compare the capabilities of different tools.
                - more detailed source code quality metrics using [SonarQube Cloud](https://www.sonarsource.com/products/sonarcloud/).
                - linked publication citations, for those tools with associated peer-reviewed publications.

                If you have any feedback or suggestions, please don't hesitate to reach out by [opening an issue on GitHub](https://github.com/open-energy-transition/openmod-tracker/issues/new) or [sending us an email](mailto:info@openenergytransition.org).
                """
            )
    st.markdown(
        f"""
        The global energy transition is accelerating.
        Given the inherent complexity of energy system planning, planners rely heavily on software tools to provide quantitative evidence to support decisions.
        Open source tools are becoming increasingly prevalent and are beginning to gain traction in industry and the public sector (e.g., at [ENTSO-E](https://www.linkedin.com/posts/entso-e_energytransition-opensource-innovation-activity-7293296246813851649-2ynL)).
        It's no wonder; they are:

        ✅ freely available,

        ✅ white-box, and

        ✅ developed and maintained by world leading academic and R&D institutes.

        With an ever-growing number of mature open source energy modelling tools, the question should no longer be _whether_ to use them, but rather _which_ to use!

        With this dashboard, we aim to answer such questions as:

        ❓ Which tools are most popular in the community?

        ❓ Which tools are actively maintained and developed, and have a high [bus factor](https://en.wikipedia.org/wiki/Bus_factor)?

        ❓ Which tools have the strongest and broadest community support?

        To do so, we provide an overview of metrics associated with the source code repositories of {n_tools} open energy planning tools, inspired by [an initial prototype by David Paolella](https://github.com/dpaolella/open-model-analysis/).
        These tools have been collated from various publicly accessible tool inventories (see [our project homepage](https://github.com/open-energy-transition/openmod-tracker/) for the full list!) and filtered for only those that have accessible Git repositories.
        You can explore the tools in the table below and filter them using the sliders in the sidebar.
        """
    )
    with st.expander("Our data processing toolkit", icon="🧰"):
        st.markdown(data_processing_text, unsafe_allow_html=True)

    with st.expander("Caveats", icon="⚠️"):
        st.markdown(
            """

            1. We rely on third parties to enable us to collate tools and their metrics.
               Where we undertake the data collection directly from the tool repositories, our heuristics may not capture some things (e.g., documentation sites).
               This means some tools and / or metrics may be missing.
               If you notice this is the case, [raise an issue on our project homepage](https://github.com/open-energy-transition/openmod-tracker/issues/new).

            2. These metrics do not tell the whole story.
               For instance, a project may have documentation but we have not reviewed how comprehensive it is!

            3. We want to add more information on tools, such as the category of problem they can be used to address (the "category" column in the table above).
               However, these are manual tasks that are best undertaken by the tool maintainers themselves.
               If you are a tool maintainer, consider contributing your category here or alongside contributing your tool to the [G-PST opentools project](https://github.com/g-pst/opentools).
               We'll pick up the contribution and feed the data back through automatically to this dashboard.

            4. We have had to manually exclude some tools from our list that have been mis-categorised in the upstream inventories.
               New, mis-categorised tools may slip through our manual exclusion net, so don't be surprised if you see a tool that doesn't seem to be useful for energy system planning.
               Conversely, you may have reason to believe a tool has been manually excluded in error.
               If that's the case, [raise an issue on our project homepage](https://github.com/open-energy-transition/openmod-tracker/issues/new).
            """
        )
    st.markdown(
        f"""
        ## Open Energy Modelling Tools - Key Metrics

        **Last Update**: {latest_changes}
        """
    )


def conclusion():
    """Text to show after the app table."""
    st.markdown(
        """
        ## Key Takeaways from the Data

        - **Adoption Signals Matter**: High download counts, active contributors, and ongoing issue resolutions suggest healthy, well-maintained projects.
          However, source code activity alone can be misleading — some highly starred projects have stalled development and some with limited source code development are in heavy use in supporting planning decisions.
        - **Sustainability Risks**: Projects with fewer than 10 contributors face a higher risk of abandonment.
          A committed and broad contributor base can be hard to come by and may need to be cultivated with financial support rather than relying on it to grow naturally.
        - **Usability Gaps**: Some projects do not have builds of their tools indexed online (e.g., on PyPI or conda-forge), which may indicate poor release management and hinder long-term usability.
        - **Interoperability Potential**: Many tools serve niche roles and may only be suitable for supporting decision-making as part of a tool suite.
          This requires tools to be interoperable, using common nomenclature and data structures.

        ## Beyond Data: The Need for Qualitative Assessments

        While data helps filter out the most interesting tools, deeper investigation is needed to ensure a tool is the right fit.
        Some key qualitative factors to consider:

        - **Documentation Quality**: Are installation and usage guides clear and up to date?
        - **Community Support**: Is there an active forum, mailing list, or issue tracker?
        - **Use Cases**: Has the tool been applied in real-world projects similar to your needs?
        - **Licensing & Governance**: Is it permissively licensed (e.g., MIT) or does it enforce restrictions (e.g., GPL)?
        - **Collaboration Potential**: Can multiple stakeholders contribute effectively?

        **By combining live data tracking with structured qualitative evaluation**, the energy community can reduce wasted investments and ensure the best tools remain available for researchers, grid operators, project developers, investors and policymakers alike.

        **Have you found this platform useful, or want to see it grow in any specific way?** Share your thoughts and suggestions on our [project homepage](https://github.com/open-energy-transition/openmod-tracker/issues)!
        """
    )


def footer():
    """Footer content for the Streamlit app."""
    st.divider()
    _, col1, col2, col3, _ = st.columns([1, 1, 1, 1, 1])
    col1.image(OET_LOGO_FULL_NAME, width=300)
    col2.markdown(
        """
        © Open Energy Transition gGmbH.
        The dashboard content is licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/deed.en).
        The dashboard source code is licensed under [MIT license](https://opensource.org/license/mit).
        """
    )
    col3.markdown(
        """
        Built by [Open Energy Transition](https://openenergytransition.org/), with support by [Breakthrough Energy GRIDS](https://www.breakthroughenergy.org/).
        The information provided in this dashboard is for informational purposes only and does not constitute professional advice.
        """
    )


def main(df: pd.DataFrame):
    """Main streamlit app generator.

    Args:
        df (pd.DataFrame): Table to display in app.
    """
    reset_mode = reset()
    st.sidebar.header("Table filters", divider=True)

    util.set_state("filters", {"toggle": [], "multiselect": [], "slider": []})

    col_config = {}
    numeric_cols = []
    filters = []
    # Show missing data info and toggle for docs column
    exclude_nan = header_and_missing_value_toggle(df["Docs"], reset_mode)
    if exclude_nan:
        filters.append(util.nan_filter(df["Docs"]))

    # Add score filtering first.
    if util.get_state("score_toggle", False):
        st.sidebar.subheader("Score", help=COLUMN_HELP["Score"])
        score_slider_range = slider(df["Score"], reset_mode, plot_dist=False)

    for col in COLUMN_NAME_MAPPING.values():
        # Show missing data info and toggle for each column
        exclude_nan = header_and_missing_value_toggle(df[col], reset_mode)
        if exclude_nan:
            filters.append(util.nan_filter(df[col]))

        if util.is_datetime_column(df[col]):
            slider_range = slider(df[col], reset_mode)
            filters.append(date_range_filter(df[col], *slider_range))
            col_config[col] = st.column_config.DateColumn(col, help=COLUMN_HELP[col])

        elif util.is_numeric_column(df[col]):
            slider_range = slider(df[col], reset_mode)

            filters.append(numeric_range_filter(df[col], *slider_range))

            numeric_cols.append(col)
            col_config[col] = st.column_config.NumberColumn(
                col, help=COLUMN_HELP[col], format=NUMBER_FORMAT[col]
            )

        elif util.is_categorical_column(df[col]):
            # Categorical multiselect
            unique_values = sorted(df[col].dropna().unique().tolist())
            selected_values = multiselect(unique_values, col, reset_mode)
            filters.append(categorical_filter(df[col], selected_values))
            col_config[col] = st.column_config.TextColumn(col, help=COLUMN_HELP[col])

        elif util.is_list_column(df[col]):
            # Categorical multiselect with list column entry
            unique_values = list(set(i for j in df[col].dropna().values for i in j))
            selected_values = multiselect(unique_values, col, reset_mode)
            filters.append(list_filter(df[col], selected_values))
            col_config[col] = st.column_config.ListColumn(col, help=COLUMN_HELP[col])

    # Add tool score by combining metrics with the provided weightings
    df["Score"] = update_score_col(df[numeric_cols])
    if util.get_state("score_toggle", False):
        filters.append(numeric_range_filter(df["Score"], *score_slider_range))
        score_col_config = st.column_config.ProgressColumn(
            "Score",
            min_value=0,
            max_value=100,
            format="%.0f%%",
            help=COLUMN_HELP["Score"],
        )
    else:
        score_col_config = None
    # Display options
    col1, col2 = st.columns([3, 2])
    with col2:
        search_result = st_keyup("Find a tool by name", value="", key="search_box")
    filters.append(df["name_with_url"].str.lower().str.contains(search_result.lower()))

    filter_series = pd.concat(filters, axis=1).all(axis=1)
    df_filtered = df[filter_series].sort_values(DEFAULT_ORDER, ascending=False)

    with col1:
        message = create_filter_message()
        st.metric(f"Tools in view{message}", f"{len(df_filtered)} / {len(df)}")

    max_interactions = df["Interactions"].dropna().apply(lambda x: x.max()).max()
    col_config = {
        "name_with_url": st.column_config.LinkColumn(
            "Tool Name",
            help="Click on the tool name to navigate to its source code repository.",
            display_text=".*#(.*)",
        ),
        "Docs": st.column_config.LinkColumn(
            "Docs", display_text="📖", help=COLUMN_HELP["Docs"]
        ),
        "Score": score_col_config,
        "Interactions": st.column_config.BarChartColumn(
            "6 Month Interactions",
            y_min=0,
            y_max=max_interactions,
            help=COLUMN_HELP["Interactions"],
        ),
        **col_config,
    }
    cols_missing_config = set(col_config.keys()).symmetric_difference(
        EXTRA_COLUMNS + list(COLUMN_NAME_MAPPING.values())
    )
    assert not cols_missing_config, (
        f"Missing column configuration for {cols_missing_config}"
    )
    # Display the table
    if len(df_filtered) > 0:
        st.dataframe(
            df_filtered,
            use_container_width=True,
            hide_index=True,
            column_config=col_config,
            column_order=col_config.keys(),
        )
    else:
        st.warning(
            "No data matches the current filter criteria. Try adjusting your filters."
        )
    st.subheader("📊 Score tools your way")
    st.markdown(
        """
        You can create your own tool scores by combining the metrics that matter most to you.
        First, toggle the scoring column.
        Then, adjust the weights applied to each numeric metric to fit your preferences."""
    )
    add_scoring(numeric_cols)

    reset_button = st.sidebar.button("🔄 Reset All Filters")
    reset_mode = reset(reset_button)


if __name__ == "__main__":
    # define the path of the CSV file listing the packages to assess
    tool_stats_dir = Path(__file__).parent.parent / "inventory" / "output"
    user_stats_dir = Path(__file__).parent.parent / "user_analysis" / "output"
    readme_path = Path(__file__).parent.parent / "README.md"

    st.set_page_config(
        page_title="Tool Repository Metrics", page_icon="⚡️", layout="wide"
    )
    st.logo(
        OET_LOGO_FULL_NAME,
        size="large",
        link="https://openenergytransition.org/",
        icon_image=OET_LOGO_ABBREVIATED,
    )

    df_vis = create_vis_table(tool_stats_dir, user_stats_dir)
    g = git.cmd.Git()
    latest_changes = g.log("-1", "--pretty=%cs", tool_stats_dir / "stats.csv")

    data_processing_approach_string = extract_processing_approach_from_readme(
        readme_path, "Our data processing approach"
    )
    preamble(latest_changes, len(df_vis), data_processing_approach_string)
    main(df_vis.copy())
    conclusion()
    footer()
