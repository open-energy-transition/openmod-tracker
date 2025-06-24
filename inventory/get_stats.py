"""Get ecosyste.ms stats for defined projects."""

import logging
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import click
import pandas as pd
import requests
import util
import yaml
from tqdm import tqdm

NOW = datetime.now()
LOGGER = logging.getLogger(__name__)
ENTRIES_TO_KEEP = [
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
# HACK: the previous month's Anaconda data doesn't get compiled and uploaded to S3 until sometime into the following month.
# Guessing 7 days in here but don't know for sure.
if NOW.day < 7:
    LAST_MONTH = NOW.month - 2
else:
    LAST_MONTH = NOW.month - 1

CONDA_DOWNLOAD_DF = pd.read_parquet(
    f"s3://anaconda-package-data/conda/monthly/{NOW.year}/{NOW.year}-{LAST_MONTH:02d}.parquet"
)
JULIA_STATS_API = "https://juliapkgstats.com/api/v1/monthly_downloads/"


def get_ecosystems_entry_data(urls: Iterable) -> pd.DataFrame:
    """Get data about repositories and associated packages from ecosyste.ms.

    Known issues:
    - Some repo hostnames are not available
    - Lots of package ecosystems have no download statistics.
      We have a hack for conda packages, but julia and java packages may have issues that are not resolved.
    - Non-github hosts have no commit data (for a DDS)
    - PyPi downloads statistics are for last month (or _the_ last month?) only, not total.

    Args:
        urls (Iterable): Iterable of URLs to search.

    Returns:
        pd.DataFrame: Collated data from ecosyste.ms for the given URLs
    """
    repo_dfs = []
    for url in tqdm(urls):
        repo_data = util.get_ecosystems_repo_data(url)
        if repo_data is None:
            LOGGER.warning(f"Could not find ecosyste.ms entry for {url}")
            continue
        else:
            repo_data_to_keep = {}
            for entry in ENTRIES_TO_KEEP:
                if "." in entry:
                    val = _get_nested_dict_entry(repo_data, entry)
                else:
                    val = repo_data[entry]
                repo_data_to_keep[entry] = val
            repo_df = pd.DataFrame(repo_data_to_keep, index=[url])

        package_data = _get_package_data(url)
        docs_data = _get_docs_data(repo_data["html_url"])
        repo_dfs.append(repo_df.assign(**package_data).assign(**docs_data))

    return pd.concat(repo_dfs)


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
    package_response = util.get_ecosystems_package_data(url)
    if package_response.ok and (
        package_data := yaml.safe_load(package_response.content.decode("utf-8"))
    ):
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
                LOGGER.warning(
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
    else:
        LOGGER.warning(f"Could not find ecosyste.ms package entry for {url}")
        filtered_package_data = {}
    return filtered_package_data


def _get_docs_data(url: str) -> dict:
    """Get most likely URLs for project documentation.

    We make some strong assumptions here:
    1. Projects are most likely hosted on readthedocs, github/gitlab pages, or a repo wiki.
    2. If a project name is already taken on readthedocs, the most likely alternative is `<org>-<project>`, but could also be <project> underscores replaced with dashes or `<project>-documentation` (1 known instance).
    3. Pages docs redirect to `stable` docs but may need directly requesting a `stable` page if not redirected automatically.

    Still, we don't catch everything.
    For instance, some projects have docs directories in their repositories but require manual builds or refer directly to the markdown files in that directory from their README.

    Args:
        url (str): project URL to act as the basis for docs searching

    Returns:
        dict: Dict mapping docs sources (rtd, pages, wiki) to links, if those links exist.
    """
    parsed = urlparse(url)
    host, owner, repo = (
        parsed.netloc,
        parsed.path.strip("/").split("/")[0],
        parsed.path.strip("/").split("/")[-1],
    )
    rtd_doc = f"http://{repo}.readthedocs.io"
    rtd_dash_doc = f"http://{repo.replace('_', '-')}.readthedocs.io"
    rtd_owner_doc = f"http://{owner}-{repo}.readthedocs.io"
    rtd_docs_doc = f"http://{repo}-documentation.readthedocs.io"
    rtd = (
        rtd_doc
        if _check_header(rtd_doc) and _verify_rtd(repo, url)
        else rtd_dash_doc
        if _check_header(rtd_dash_doc) and _verify_rtd(repo.replace("_", "-"), url)
        else rtd_owner_doc
        if _check_header(rtd_owner_doc) and _verify_rtd(f"{repo}-documentation", url)
        else rtd_docs_doc
        if _check_header(rtd_docs_doc) and _verify_rtd(f"{repo}-documentation", url)
        else None
    )

    pages_doc = f"http://{owner}.{host.replace('.com', '.io')}/{repo}"
    pages_doc_stable = f"http://{owner}.{host.replace('.com', '.io')}/{repo}/stable"
    pages = (
        pages_doc
        if _check_header(pages_doc)
        else pages_doc_stable
        if _check_header(pages_doc_stable)
        else None
    )

    bb_wiki_doc = f"{url}.git/wiki"
    other_wiki_doc = f"{url}.wiki.git"
    wiki = (
        bb_wiki_doc
        if (host == "bitbucket.org" and _check_header(bb_wiki_doc))
        else other_wiki_doc
        if _check_header(other_wiki_doc)
        else None
    )

    docs = {"rtd": rtd, "pages": pages, "wiki": wiki}
    if all(doc is None for doc in docs.values()):
        LOGGER.warning(f"No documentation found for {url}")
    return docs


def _check_header(url: str) -> bool:
    """Check that a `url` exists by querying the header (allowing for redirects)."""
    try:
        response = requests.head(url, allow_redirects=True)
        return response.ok
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
        return False


def _verify_rtd(slug: str, url: str) -> bool:
    """Verify that a successful readthedocs find actually refers to the Git repo we're expecting.

    We achieve this by querying the RTD API for the found docs site and checking the git repo used to generate that site against the Git repo URL we believe it should be.

    In some cases, the RTD Git URL is a redirect

    Args:
        slug (str): `readthedocs` slug, i.e. <slug>.readthedocs.io
        url (str): Git repo URL to check.

    Returns:
        bool: True if RTD Git URL linked to the `slug` site matches the `url`, False otherwise.
    """
    response = util.get_url_json_content(
        f"https://readthedocs.org/api/v3/projects/{slug.lower()}"
    )
    rtd_git_url = response.get("repository", {}).get("url", None)
    if rtd_git_url is not None:
        rtd_git_url_cleaned = requests.head(rtd_git_url, allow_redirects=True).url
        return rtd_git_url_cleaned == url
    else:
        return False


@click.command()
@click.argument("infile", type=click.Path(exists=True, dir_okay=False, file_okay=True))
@click.argument(
    "outfile", type=click.Path(exists=False, dir_okay=False, file_okay=True)
)
def cli(infile: Path, outfile: Path):
    """Get ecosyste.ms stats for all entries."""
    entries = pd.read_csv(infile)
    stats_df = get_ecosystems_entry_data(entries.url)
    stats_df.to_csv(outfile)


if __name__ == "__main__":
    cli()
