"""Scripts to grab data from different sources and process them to a common format."""

import logging
import re
from pathlib import Path

import click
import pandas as pd
import requests
import util
from bs4 import BeautifulSoup
from tqdm import tqdm

TOOL_TYPES = ["production-cost", "capacity-expansion", "power-flow", "other"]
LF_ENERGY_URL = "https://raw.githubusercontent.com/lf-energy/lfenergy-landscape/refs/heads/main/landscape.yml"
G_PST_URL = "https://api.github.com/repos/G-PST/opentools/contents/data/software"
OST_URL = (
    "https://docs.getgrist.com/api/docs/gSscJkc5Rb1Rw45gh1o1Yc/tables/Projects/data"
)
OPENMOD_URL = "https://wiki.openmod-initiative.org/wiki/Open_Models"

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
        if i["name"] in ["Modeling and Optimization", "Power System Calculation"]
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
        .isin(["Energy System Modeling Frameworks", "Grid Analysis and Planning"]),
        ["git_url", "description", "project_names"],
    ]
    return filtered_df.rename(
        columns={"git_url": "url", "project_names": "name"}
    ).assign(source="opensustain-tech")


def get_openmod() -> pd.DataFrame:
    """Get Open Energy Modelling Initiative wiki Open Models list.

    Returns:
        pd.DataFrame: Openmod wiki list entries and their associated Source Download URL.
    """
    response = requests.get(OPENMOD_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    list_of_models_start = soup.find("span", {"id": "List_of_models"})
    if list_of_models_start is None:
        LOGGER.warning("Could not find list of openmod models")
        return pd.DataFrame()

    for elem in list_of_models_start.next_elements:
        if hasattr(elem, "li"):
            list_of_models = elem.find_all("a")
            break
    urls = []
    not_found = []
    LOGGER.warning("Scraping openmod entries.")
    for i in tqdm(list_of_models):
        response_child = requests.get(
            "https://wiki.openmod-initiative.org" + i.attrs["href"]
        )
        soup_child = BeautifulSoup(
            response_child.content.decode("utf-8"), "html.parser"
        )
        url = _get_openmod_model_property(soup_child, "Source download")
        if url is None:
            not_found.append(i.attrs["title"])
        if url is not None:
            # HACK: there are known URLs that are _almost_ valid Git URLs, so we clean them up here.
            if "/-/" in url:
                url = url.split("/-/")[0]
            elif "codeload.github" in url:
                url = url.replace("codeload.", "").split("/zip/")[0]

        description = _get_openmod_model_property(soup_child, "Text description")
        urls.append({"name": i.attrs["title"], "url": url, "description": description})
    if not_found:
        LOGGER.warning(
            f"No source code URL found for the following openmod models: {'\n'.join(not_found)}"
        )

    df = pd.DataFrame(urls)
    return df.assign(source="openmod")


def _get_openmod_model_property(soup: BeautifulSoup, prop_name: str) -> str | None:
    """Get content for a named property in an openmod model "factsheet".

    Args:
        soup (BeautifulSoup): Parsed model page HTML.
        prop_name (str): Property name to return content for (if available)

    Returns:
        str | None: Content of model factsheet `prop_name`.
    """
    prop_elem = soup.find("a", {"title": f"Property:{prop_name}"})
    if prop_elem is not None and prop_elem.next.next.text != "":
        prop = prop_elem.next.next.text.removesuffix(" +")
        if " … " in prop:
            prop = prop.split(" … ")[1]
    else:
        prop = None
    return prop


def load_pre_compiled_list() -> pd.DataFrame:
    """Load pre-compiled URL list stored within this repository, derived from https://doi.org/10.1016/j.rser.2018.11.020 and subsequent searches.

    Returns:
        pd.DataFrame: Pre-compiled list with tool names based on URL content.
    """
    pre_compiled_list = pd.read_csv(Path(__file__).parent / "pre_compiled_esm_list.csv")
    names = pre_compiled_list.source_url.apply(lambda x: Path(x.strip("/")).stem)
    df = pd.DataFrame({"url": pre_compiled_list.source_url, "name": names})

    return df.assign(source="manual")


def add_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Add manually derived tool categories.

    Args:
        df (pd.DataFrame): Tools table.

    Returns:
        pd.DataFrame: Updated `df` with `category` column filled with manual categories.
    """
    categories = pd.read_csv(
        Path(__file__).parent / "categories.csv", index_col="id"
    ).category
    df = df.set_index("id")
    df["category"] = df["category"].fillna(categories.reindex(df.index))
    return df.reset_index()


@click.command()
@click.argument(
    "outfile", type=click.Path(exists=False, dir_okay=False, file_okay=True)
)
def cli(outfile: Path):
    """Get latest ESM list from various sources."""
    automatic_entries = pd.concat(
        [
            get_lf_energy_landscape(),
            get_opensustaintech(),
            get_g_pst_opentools(),
            get_openmod(),
        ]
    )

    manual_entries = load_pre_compiled_list()

    entries = pd.concat([automatic_entries, manual_entries])
    # Clean up URLs
    entries["url"] = (
        entries["url"]
        .astype(str)
        .apply(lambda x: x.strip("/").lower())
        .apply(lambda x: "https://" + x if not x.startswith("http") else x)
        .where(entries["url"].notnull())
    )

    entries["id"] = entries.name.map(
        lambda x: re.sub(r"\s|\-|\.", "_", str(x).strip().lower())
    )

    entries = add_categories(entries)

    entries.to_csv(outfile, index=False)


if __name__ == "__main__":
    cli()
