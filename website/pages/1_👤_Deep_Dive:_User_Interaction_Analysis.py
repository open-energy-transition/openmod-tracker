"""Create Streamlit web app sub-page to visualise tool user data.

(C) Open Energy Transition (OET)
License: MIT / CC0 1.0
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

KEEP_TOP = 15


def create_vis_table(user_stats_dir: Path) -> pd.DataFrame:
    """Load vis table."""
    # Check if user analysis data exists
    user_classifications = user_stats_dir / "user_classifications.csv"

    class_df = pd.read_csv(user_classifications)

    # update streamlit session state doe use in the user interaction deep-dive page
    return class_df


def user_pie(user_stats_df: pd.DataFrame):
    """Prepare plot to show distribution of user classifications."""
    # Create pie chart of classifications
    st.subheader("User Types Across All Repositories")
    class_counts = user_stats_df.classification.value_counts()

    fig = px.pie(
        values=class_counts.values,
        names=class_counts.index,
        title=f"Distribution of {len(user_stats_df)} Users by Type",
        color_discrete_sequence=px.colors.qualitative.Plotly,
    )
    st.plotly_chart(fig, key="user_types_pie")


def org_bar(user_stats_df: pd.DataFrame):
    """Prepare plot to show orgs to which users are affiliated."""
    st.subheader("Top Organizations Engaging with Repositories")

    # Sort organizations by count
    org_counts = user_stats_df.company.value_counts().head(KEEP_TOP)

    fig = px.bar(
        org_counts.to_frame("Number of Users").reset_index(),
        x="company",
        y="Number of Users",
        title=f"Top {KEEP_TOP} Organizations",
        color="Number of Users",
        color_continuous_scale=px.colors.sequential.Viridis,
    )
    fig.update_layout(xaxis_tickangle=-45, xaxis={"title": "Organization"})
    st.plotly_chart(fig, key="top_orgs_bar")


def user_locations(user_stats_df: pd.DataFrame):
    """Prepare plots to show user locations (i.e. countries)."""
    locations_count = user_stats_df.location.value_counts().head(KEEP_TOP)
    fig = px.bar(
        locations_count.to_frame("Number of Users").reset_index(),
        x="location",
        y="Number of Users",
        title=f"Top {KEEP_TOP} Locations",
        color="Number of Users",
        color_continuous_scale=px.colors.sequential.Viridis,
    )
    fig.update_layout(xaxis_tickangle=-45, xaxis={"title": "Location"})
    st.plotly_chart(fig, key="top_locations_bar")

    # Add a world map visualization
    st.subheader("Geographic Map")

    fig = px.choropleth(
        locations_count.rename_axis(index="country")
        .to_frame("Number of Users")
        .reset_index(),
        locations="country",
        locationmode="country names",
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
    st.plotly_chart(fig, key="country_map")


def _repo_to_tool_map(user_stats_df: pd.DataFrame) -> list[dict]:
    available_repos = set((",".join(user_stats_df.repos.values)).split(","))
    tools_df = pd.read_csv(
        Path(__file__).parent.parent.parent / "inventory" / "output" / "filtered.csv"
    )

    repo_to_tool_map = [
        {
            "repo": repo,
            "name": tools_df.loc[
                tools_df.url == "https://github.com/" + repo.lower(), "name"
            ]
            .item()
            .split(",")[0],
        }
        for repo in available_repos
    ]

    return repo_to_tool_map


def preamble():
    """Text to show before the user data plots."""
    st.markdown(
        """
        # Tool User Interaction Analysis

        A wide variety of users interact with the hosted repositories of each of our tracked energy modelling tools.
        These interactions generally come in the form of [stars](https://docs.github.com/en/get-started/exploring-projects-on-github/saving-repositories-with-stars), [forks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-forks), [watches](https://dl.acm.org/doi/10.1145/2597073.2597114), [issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/about-issues), and [contributions](https://docs.github.com/en/repositories/viewing-activity-and-data-for-your-repository/viewing-a-projects-contributors#about-contributors).
        On this page, we have collated all these interactions for all GitHub-hosted tools.
        We have then gathered data on the GitHub users linked to those interactions to find their origin country and attempted to classify them as being from one of 5 main groups:

        - 🎓 **academic** - an academic institution (e.g., university).
        - 🏦 **financial** - a financial institution (e.g., bank).
        - 🏬 **government** - a government department.
        - 🏭 **industry** - an energy industry actor (e.g., wind turbine manufacturer).
        - 👩‍💻 **professional** - a consultancy / professional interest group (incl. self-employed).
        - 🔎 **research** - a non-academic research institution (e.g. a US national lab).
        - 💡 **utility** - an energy industry public/private utility company or system operator (e.g. a transmission system operator)

        Here, you can explore the result of our user interaction analysis for each tool (or any set of tools).
        In doing so, you may find out more about:

        - how much interaction a tool is getting within and outside academia.
        - which organisations are most involved with a tool.
        - the geographic diversity of tool interaction, especially how far the reach of the tool is beyond its "home" country.

        Whether you're a tool maintainer looking to understand your reach, a potential tool user exploring the size of the community in your country, or a financier quantifying the value of investing in tool development, we hope you find this analysis interesting!
        """
    )
    with st.expander("Caveats", icon="⚠️"):
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


def main(user_stats_df: pd.DataFrame):
    """Load page."""
    # Select repository to view
    repo_to_tool_map = _repo_to_tool_map(user_stats_df)
    all_tools_toggle = st.sidebar.toggle("Show analysis for all tools", value=True)
    selected_tools = st.sidebar.multiselect(
        "Select repositories to analyze in aggregate",
        options=sorted([i["name"] for i in repo_to_tool_map]),
        disabled=all_tools_toggle,
    )
    if not all_tools_toggle:
        if selected_tools:
            user_stats_df = user_stats_df[
                user_stats_df.repos.str.contains(
                    "|".join(
                        i["repo"]
                        for i in repo_to_tool_map
                        if i["name"] in selected_tools
                    )
                )
            ]
        else:
            st.warning("No data to show")
            user_stats_df = pd.DataFrame()

    if not user_stats_df.empty:
        user_pie(user_stats_df)

        org_bar(user_stats_df)

        if user_stats_df.location.notnull().any():
            user_locations(user_stats_df)


if __name__ == "__main__":
    # define the path of the CSV file listing the packages to assess
    user_stats_dir = Path(__file__).parent.parent.parent / "user_analysis" / "output"
    df_vis = create_vis_table(user_stats_dir)

    st.set_page_config(
        page_title="User Interaction Analysis", page_icon="👤", layout="wide"
    )
    preamble()
    main(df_vis)
