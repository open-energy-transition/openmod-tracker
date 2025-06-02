"""Scripts to grab data from different sources and process them to a common format."""

import logging
from pathlib import Path

import pandas as pd
import util
from tqdm import tqdm

TOOL_TYPES = ["production-cost", "capacity-expansion", "power-flow", "other"]
SOURCES = ["lf-energy-landscape", "g-pst", "opensustain-tech"]
LF_ENERGY_URL = "https://raw.githubusercontent.com/lf-energy/lfenergy-landscape/refs/heads/main/landscape.yml"
G_PST_URL = "https://api.github.com/repos/G-PST/opentools/contents/data/software"
OST_URL = (
    "https://docs.getgrist.com/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/tables/Projects/data"
)

LOGGER = logging.getLogger(__file__)


def get_lf_energy_landscape() -> pd.DataFrame:
    """Get data from the LF-Energy Landscape project.

    This project is a parallel project to OpenSustain.tech which periodically loads in OpenSustain.tech data.
    It then has additional projects.

    Compared to other projects:

    - It contains more user-defined metadata per project than OpenSustain.tech.
    - It attempts to collate metadata on the organisations that _manage_ tools, using [crunchbase](https://www.crunchbase.com/).
      However, on checking a random sample, this can be quite wrong (e.g. a PhD/PostDoc project that is specified as owned by the most recent University they worked at.).
    - It stores some data that can be accessed on-the-fly by ecosyste.ms, e.g., license.
    - It has tools that would not be recognised by ecosyste.ms, e.g., if source code is hosted on GitLab.

    Returns:
        pd.DataFrame: "Energy Systems / Modeling and Optimization" tools, filtered to just [name, description, repo_url/homepage_url].
    """
    lf_energy_dict = util.get_url_json_content(LF_ENERGY_URL)["landscape"]

    lf_energy_es_dict = [i for i in lf_energy_dict if i["name"] == "Energy Systems"][0]
    lf_energy_esm_dict = [
        i
        for i in lf_energy_es_dict["subcategories"]
        if i["name"] == "Modeling and Optimization"
    ][0]["items"]
    inventory_entries = []
    for entry in lf_energy_esm_dict:
        inventory_entries.append(
            {
                "name": entry["name"],
                "description": entry.get("description", None),
                "url": entry.get("repo_url", entry.get("homepage_url", None)),
            }
        )
    return pd.DataFrame(inventory_entries).assign(source="lf-energy-landscape")


def get_g_pst_opentools():
    """Get data from the G-PST opentools project.

    This project contains tools which have been manually added by contributors.
    No data is inferred automatically.

    Compared to other projects:

    - It as an Energy System Modelling focus, so tool metadata includes the "categories" parameter with which to subset tools into the types of problems they could be used to solve.
    - The user input requirement does ensure that some key metadata is probably the most "correct" of the available data sources (e.g., Python tools can be mis-labelled as Jupyter Notebook tools by ecosyste.ms)
    - It has no automated system to keep tool information up-to-date.
    - It does not _require_ some key entries such as a tool URL.

    Returns:
        pd.DataFrame: Any tools with which have been categorised as a capacity expansion, production cost, or power flow model.
                      data is filtered to just [name, description, url_sourcecode, categories].
    """
    tools = util.get_url_json_content(G_PST_URL)
    tools_data = []
    for tool in tools:
        tool_data = util.get_url_json_content(tool["download_url"])
        if not any(i in TOOL_TYPES for i in tool_data.get("categories", [])):
            continue
        tools_data.append(
            {
                "name": tool_data["name"],
                "url": tool_data.get("url_sourcecode"),
                "description": tool_data.get("description"),
                "category": ",".join(
                    [i for i in tool_data["categories"] if i in TOOL_TYPES]
                ),
            }
        )

    return pd.DataFrame(tools_data).assign(source="g-pst")


def get_opensustaintech() -> pd.DataFrame:
    """Get data from the OpenSustain.tech project.

    This project contains a wealth of tools, of which ESMs are only a sub-category, which have passed an initial check for their use to the open source community.

    Compared to other projects:

    - It is the best known of the tool data sources from which we're extracting.
    - It is well integrated with ecosyste.ms.
    - We can grab ecosyste.ms-derived data outputs (incl. package downloads) when we extract other metadata.

    Returns:
        pd.DataFrame: "Energy Systems / Energy System Modeling Frameworks" and "Energy Systems / Grid Analysis and Planning" tools, filtered to just [name, description, git_url]
    """
    opensustaintech_df = pd.DataFrame(util.get_url_json_content(OST_URL))
    filtered_df = opensustaintech_df.loc[
        opensustaintech_df["sub_category"]
        # Data is stored in lists of the form `['L', 'Grid Analysis and Planning']`, we only want the second one.
        .map(lambda x: x[1])
        .isin(
            ["Energy System Modeling Frameworks", "Grid Analysis and Planning"],
        ),
        ["git_url", "description", "project_names"],
    ]
    return filtered_df.rename(
        columns={"git_url": "url", "project_names": "name"}
    ).assign(source="opensustain-tech")


def load_manual_list(current_urls: list[str]) -> pd.DataFrame:
    """Load manual list stored within this repository, derived from https://doi.org/10.1016/j.rser.2018.11.020 and subsequent searches.

    Args:
        current_urls (list[str]): List of URLs already collected from other repositories.
        These will be taken as valid repos, to reduce the number of required calls to ecosyste.ms.
    Returns:
        pd.DataFrame: List filtered to those that have corresponding ecosyste.ms entries.
    """

    manual_list = pd.read_csv(Path(__file__).parent / "manual_esm_list.csv")
    filtered_df = pd.DataFrame()
    for entry in tqdm(manual_list["source_url"].str.strip("/").str.lower()):
        if not entry.startswith("http"):
            entry = "https://" + entry
        if entry in current_urls or util.get_ecosystems_repo_data(entry).ok:
            entry_name = entry.split("/")[-1]
            filtered_df = pd.concat(
                [filtered_df, pd.DataFrame({"url": [entry], "name": [entry_name]})]
            )

    return filtered_df.assign(source="manual")
