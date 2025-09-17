# SPDX-FileCopyrightText: openmod-tracker contributors listed in AUTHORS.md
#
# SPDX-License-Identifier: MIT


"""Get ecosyste.ms stats for defined projects."""

import logging
from datetime import datetime
from pathlib import Path

import click
import pandas as pd
import util
from tqdm import tqdm

NOW = datetime.now()
LOGGER = logging.getLogger(__name__)
ENTRIES_TO_KEEP = [
    "html_url",
    "owner",
    "archived",
    "stargazers_count",
    "forks_count",
    "language",
    "license",
    "created_at",
    "updated_at",
    "commit_stats.dds",
    "commit_stats.total_committers",
    "homepage",
]
EXTRA_COLS = [
    "last_month_downloads",
    "dependent_repos_count",
    "latest_release_published_at",
]
LAST_MONTH = NOW.month - 1
try:
    # The previous month's Anaconda data doesn't get compiled and uploaded to S3 until sometime into the following month.
    # If the file isn't found, we take the month before that
    CONDA_DOWNLOAD_DF = pd.read_parquet(
        f"s3://anaconda-package-data/conda/monthly/{NOW.year}/{NOW.year}-{LAST_MONTH:02d}.parquet"
    )
except FileNotFoundError:
    CONDA_DOWNLOAD_DF = pd.read_parquet(
        f"s3://anaconda-package-data/conda/monthly/{NOW.year}/{NOW.year}-{LAST_MONTH - 1:02d}.parquet"
    )

JULIA_STATS_API = "https://juliapkgstats.com/api/v1/monthly_downloads/"


def get_ecosystems_entry_data(
    tools: pd.DataFrame, existing_data: pd.DataFrame
) -> pd.DataFrame:
    """Get data about repositories and associated packages from ecosyste.ms.

    Known issues:
    - Some repo hostnames are not available
    - Lots of package ecosystems have no download statistics.
      We have a hack for conda packages, but julia and java packages may have issues that are not resolved.
    - Non-github hosts have no commit data (for a DDS)
    - PyPi downloads statistics are for last month (or _the_ last month?) only, not total.

    Args:
        tools (pd.DataFrame): tools to search. `id` & `url` columns are used.
        existing_data (pd.DataFrame): Existing data for all / most URLs, to fill in for server-side errors (which are common).

    Returns:
        pd.DataFrame: Collated data from ecosyste.ms for the given URLs
    """
    repo_dfs = []
    for _, tool in tqdm(tools.iterrows(), total=len(tools)):
        repo_data = util.get_ecosystems_repo_data(tool.url)

        if repo_data == "not-found":
            LOGGER.warning(f"No ecosyste.ms entry for {tool.id} ({tool.url})")
            continue
        if repo_data is None:
            if tool.id in existing_data.index:
                suffix = "; using older data"
                repo_dfs.append(existing_data.loc[[tool.id]])
            else:
                suffix = ""
            LOGGER.warning(
                f"Could not access ecosyste.ms entry for {tool.id} ({tool.url}){suffix}."
            )
            continue

        repo_data_to_keep = {}
        for entry in ENTRIES_TO_KEEP:
            if "." in entry:
                val = _get_nested_dict_entry(repo_data, entry)
            else:
                val = repo_data[entry]
            repo_data_to_keep[entry] = val
        repo_df = pd.DataFrame(repo_data_to_keep, index=pd.Index([tool.id], name="id"))

        package_data = _get_package_data(repo_data["html_url"])
        repo_dfs.append(repo_df.assign(**package_data))

    if repo_dfs:
        return pd.concat(repo_dfs)
    else:
        return pd.DataFrame()


def _get_nested_dict_entry(
    nested_dict: dict, attr_key: str
) -> str | int | bool | float | None:
    """Get nested dict entry based on a dot separated set of keys.

    Args:
        nested_dict (dict): Dictionary with nested sub-dicts.
        attr_key (str): dot separated key names.

    Returns:
        str | int | bool | float | None: Content of sub-dictionary. If the nested key is not found, will return None.

    Example:
        ```py
        nested_dict = {"foo": {"bar": 1}}
        attr_key = "foo.bar"
        _get_nested_dict_entry(nested_dict, attr_key)
        [OUT]: 1
        ```
    """
    key_1, key_2 = attr_key.split(".", 1)
    subdict = nested_dict.get(key_1, None)
    if not isinstance(subdict, dict):
        val = None
    elif "." in key_2:
        val = _get_nested_dict_entry(subdict, key_2)
    else:
        val = subdict.get(key_2, None)
    return val


def _get_package_data(url: str) -> dict:
    package_data = util.get_ecosystems_package_data(url)
    if package_data is None or package_data == "not-found":
        LOGGER.warning(f"Could not find ecosyste.ms package entry for {url}")
        filtered_package_data = {}
    else:
        download_count_all = 0
        latest_release_all = None
        dependent_repos_count_all = 0
        for package_source in package_data:
            if package_source["ecosystem"] == "conda":
                # HACK: last month download count doesn't seem to exist in ecosyste.ms
                download_count_all += CONDA_DOWNLOAD_DF[
                    CONDA_DOWNLOAD_DF.pkg_name == package_source["name"]
                ].counts.sum()
            elif package_source["ecosystem"] == "julia":
                # Julia download stats don't seem to exist in ecosyste.ms (always returning null)
                julia_downloads = util.get_url_json_content(
                    JULIA_STATS_API + package_source["name"]
                )["total_requests"]
                download_count_all += int(julia_downloads)
            elif (
                pd.notnull(package_source["downloads"])
                and package_source["downloads_period"] == "last-month"
            ):
                download_count_all += package_source["downloads"]
            else:
                LOGGER.debug(
                    f"Found null package downloads for {package_source['name']} from {package_source['ecosystem']}"
                )
            latest_release = pd.to_datetime(
                package_source["latest_release_published_at"]
            )
            if latest_release_all is None or latest_release > latest_release_all:
                latest_release_all = latest_release
            dependent_repos_count = package_source["dependent_repos_count"]
            if pd.notnull(dependent_repos_count) and (
                dependent_repos_count > dependent_repos_count_all
            ):
                dependent_repos_count_all = dependent_repos_count

        filtered_package_data = {
            "last_month_downloads": download_count_all,
            "dependent_repos_count": dependent_repos_count_all,
        }
        if latest_release_all is not None:
            filtered_package_data["latest_release_published_at"] = (
                latest_release_all.strftime("%Y-%m-%d")
            )
    return filtered_package_data


@click.command()
@click.argument(
    "infile",
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
)
@click.argument(
    "outfile",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
)
@click.option("--find-missing", is_flag=True)
def cli(infile: Path, outfile: Path, find_missing: bool):
    """Get ecosyste.ms stats for all entries."""
    entries = pd.read_csv(infile)
    if outfile.exists():
        existing_stats_df = pd.read_csv(outfile, index_col="id")
    else:
        existing_stats_df = pd.DataFrame()

    if find_missing:
        entries = entries[~entries.id.isin(existing_stats_df.index)]

    stats_df = get_ecosystems_entry_data(entries, existing_stats_df)

    if find_missing:
        stats_df = pd.concat([stats_df, existing_stats_df])

    stats_df[ENTRIES_TO_KEEP + EXTRA_COLS].sort_index().to_csv(outfile)


if __name__ == "__main__":
    cli()
