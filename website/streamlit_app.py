"""Update package history based on latest available statistics from ecosyste.ms and anaconda.

(C) Open Energy Transition (OET)
License: MIT / CC0 1.0
"""

# import required packages
from datetime import datetime
from pathlib import Path

import pandas as pd
from itables.streamlit import interactive_table
from streamlit import markdown, set_page_config

COLUMN_NAME_MAPPING = {
    "created_at": "Created",
    "updated_at": "Updated",
    "stargazers_count": "Stars",
    "commit_stats.total_committers": "Contributors",
    "commit_stats.dds": "DDS",
    "forks_count": "Forks",
    "dependent_repos_count": "Dependents",
    "last_month_downloads": "Last Month Downloads",
}


def create_vis_table(tool_data_dir: Path) -> pd.DataFrame:
    """Create the tool table with columns renamed and filtered ready for visualisation.

    Args:
        tool_data_dir (Path): The directory in which to find tool list and stats.

    Returns:
        pd.DataFrame: Filtered and column renamed tool table.
    """
    stats_df = pd.read_csv(tool_data_dir / "stats.csv", index_col=0)
    tools_df = pd.read_csv(tool_data_dir / "filtered.csv", index_col="url")
    df = (
        pd.merge(left=stats_df, right=tools_df, right_index=True, left_index=True)
        .rename_axis(index="url")
        .reset_index()
    )

    # Assume: majority Jupyter Notebook projects are actually Python projects.
    df["language"] = df.language.replace({"Jupyter Notebook": "Python"})
    df["Project Name"] = (
        "<a href=" + df.url + ">" + df.name.apply(lambda x: x.split(",")[0]) + "</a>"
    )
    for timestamp_col in ["created_at", "updated_at"]:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col]).dt.date
    df_vis = df.rename(columns=COLUMN_NAME_MAPPING)[
        ["Project Name"] + list(COLUMN_NAME_MAPPING.values())
    ]
    return df_vis


def update_esm_analysis(df_vis: pd.DataFrame, latest_changes: str):
    """Create streamlit page to view tool information extracted from ecosyste.ms.

    Args:
        df_vis (pd.DataFrame): Prepared stats table.
        latest_changes (str): timestamp string corresponding to the most recent update to the stats table.
    """
    # add some text before the interactive table
    markdown(
        f"""
        # Smarter Investments in Open Energy Planning: How Data Can Guide Decision-Makers

        This analysis is available at OET's [open-esm-analysis GitHub repository](https://github.com/open-energy-transition/open-esm-analysis/).

        The global energy transition is moving fast, but so are the challenges in directing time and resources effectively.
        Achieving international climate goals will require around **4.5 trillion in annual investments** by the early 2030s.
        To optimize infrastructure investments, grid operations and policy decisions, open-source tools are becoming the 'goat' in the room with increasing adoption across all sectors (see e.g. this [ENTSO-E post on LinkedIn](https://www.linkedin.com/posts/entso-e_energytransition-opensource-innovation-activity-7293296246813851649-2ynL)).

        However, with an ever-growing number of open-source (OS) energy tools, the question remains: **How do decision-makers - whether researchers, funders, or grid operators - select the right tools for their needs?**
        The answer lies in data combined with experience.

        ## The Challenge: Identifying Reliable and Impactful Tools

        Funders and users alike need to distinguish between active, well-maintained tools and those that might no longer be viable. While qualitative reviews (user feedback, case studies, etc.) are valuable, quantitative metrics offer critical signals about a tool's reliability, sustainability, and adoption.

        The table below highlights key statistics for several leading OS energy planning tools, offering a snapshot of their development activity, usage, and maintenance.
        These tools have been collated from various publicly accessible tool inventories (see [our project homepage](https://github.com/open-energy-transition/open-esm-analysis/) for the full list!) and filtered for only those that have accessible Git repositories.

        **Table 1: Open-Source ESM Tools - Key Data Indicators** (Data: ecosystem.ms; Last Update: {latest_changes}; Default Order: Number of Stars (descending))
        """
    )

    # add the interactive table
    interactive_table(
        df_vis.sort_values("Stars", ascending=False),
        lengthMenu=[25, 50],
        buttons=["copyHtml5", "csvHtml5", "excelHtml5", "colvis"],
        allow_html=True,
        showIndex=False,
    )

    markdown(
        """
        (*Created: first repository commit; Updated: last repository commit; Stars: GitHub bookmarks; Contributors: active source code contributors; DDS: development distribution score (the bigger the number the better; but 0 means no data available); Forks: number of Git forks; Dependents: packages dependent on this project; Last Month Downloads: package installs last month*)

        ## Key Takeaways from the Data

        - **Adoption Signals Matter**: High download counts, active contributors, and ongoing issue resolutions suggest healthy, well-maintained projects. However, GitHub stars alone can be misleading—some highly starred projects have stalled development."
        - **Sustainability Risks**: Projects with fewer than 10 contributors face a higher risk of abandonment. Also depending on packages with a small number of contributors might be a risk for the project. Funders should be wary of investing in tools that lack a committed maintainer base.
        - **Transparency Gaps**: Some projects do not disclose key statistics (e.g., download counts), which may indicate poor release management and hinder long-term usability.
        - **Interoperability Potential**: Many tools serve niche roles, but interoperability—how well they integrate with others—is becoming a crucial factor for large-scale adoption.

        ## Beyond Data: The Need for Qualitative Assessments

        While data helps filter out unreliable tools, deeper investigation is needed to ensure a tool is the right fit. Some key qualitative factors to consider:

        - **Documentation Quality**: Are installation and usage guides clear and up to date?
        - **Community Support**: Is there an active forum, mailing list, or issue tracker?
        - **Use Cases**: Has the tool been applied in real-world projects similar to your needs?
        - **Licensing & Governance**: Is it permissively licensed (e.g., MIT) or does it enforce restrictions (e.g., GPL)?
        - **Collaboration Potential**: Can multiple stakeholders contribute effectively?

        ## The Case for a Live Decision-Support Platform

        Right now, there is no single source of truth for assessing the viability of open-source energy planning tools.
        An up-to-date, data-driven decision-support platform could bridge this gap, providing real-time insights on:

        - **Maintenance health** (contributor activity, unresolved issues)
        - **Adoption rates** (downloads, citations, user engagement)
        - **Tool interoperability** (compatibility testing with other OS models)
        - **Funding needs** (identifying tools at risk due to lack of maintainers)

        Such a platform would empower funders to invest wisely, helping direct resources to projects with the highest impact potential.

        Selecting the right OS energy planning tool is no longer just a technical choice — it's an **investment decision**.
        While **data-driven insights can highlight adoption trends, sustainability risks, and tool maturity**, *qualitative assessments remain essential for selecting the best fit*.

        **By combining live data tracking with structured qualitative evaluation**, the energy community can reduce wasted investments and ensure the best tools remain available for researchers, grid operators, project developers, investors and policymakers.

        **Would you find a real-time OS tool insight platform useful?** Share your thoughts and suggestions in the comments or the [issues tracker](https://github.com/open-energy-transition/open-esm-analysis/issues)!

        """
    )


if __name__ == "__main__":
    # define the path of the CSV file listing the packages to assess
    output_dir = Path(__file__).parent.parent / "inventory" / "output"
    df_vis = create_vis_table(output_dir)
    latest_changes = datetime.fromtimestamp(output_dir.stat().st_ctime).strftime(
        "%Y-%m-%d"
    )

    set_page_config(layout="wide")
    update_esm_analysis(df_vis, latest_changes)
