# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Get ecosyste.ms stats for defined projects."""

import logging
import os
from pathlib import Path
from time import sleep
from urllib.parse import urlparse

import click
import dotenv
import pandas as pd
import requests
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)
COLS = ["rtd", "pages", "wiki"]
RTD_URL = "http://{slug}.readthedocs.io"


def _parse_url(url: str) -> tuple[str, str, str]:
    """Parse a Git repo URL into its host, owner, and repo components."""
    parsed = urlparse(url)
    host, owner, repo = (
        parsed.netloc,
        parsed.path.strip("/").split("/")[0],
        parsed.path.strip("/").split("/")[-1],
    )
    return host, owner, repo


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
    host, owner, repo = _parse_url(url)

    for rtd_slug in [
        repo,
        repo.replace("_", "-"),
        owner,
        owner.replace("_", "-"),
        f"{owner}-{repo}",
        f"{repo}-documentation",
        f"{repo}-docs",
    ]:
        valid_rtd_doc = _verify_rtd(rtd_slug, url)
        if valid_rtd_doc:
            rtd = RTD_URL.format(slug=rtd_slug)
            break
        else:
            rtd = None

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
    token = os.getenv("READTHEDOCS_API_TOKEN")
    if token is not None:
        kwargs = {"headers": {"Authorization": f"Token {token}"}}
    else:
        kwargs = {}
    try:
        url_status = requests.get(RTD_URL.format(slug=slug)).status_code
    except requests.exceptions.SSLError:
        LOGGER.warning(
            f"SSL error when checking {slug}.readthedocs.io. Skipping RTD check for this slug."
        )
        return False

    if url_status == 404:
        return False
    elif url_status == 429:
        LOGGER.warning(
            f"Rate limited by RTD when checking {slug}. Waiting 60 seconds before retrying."
        )
        sleep(60)
        return _verify_rtd(slug, url)

    response = requests.get(
        f"https://readthedocs.org/api/v3/projects/{slug.lower()}", **kwargs
    )

    if response.status_code == 429:
        LOGGER.warning(
            f"Rate limited by RTD API when checking {slug}. Waiting 60 seconds before retrying."
        )
        sleep(60)
        return _verify_rtd(slug, url)
    elif not response.ok:
        return False

    rtd_git_url = response.json().get("repository", {}).get("url", None)
    host, owner, _ = _parse_url(url)
    url_org = f"https://{host}/{owner}/documentation"
    if rtd_git_url is not None:
        try:
            rtd_git_url_cleaned = (
                requests.head(rtd_git_url, allow_redirects=True)
                .url.removesuffix(".git")
                .lower()
            )
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
            return False
        return (
            rtd_git_url_cleaned == url.lower() or rtd_git_url_cleaned == url_org.lower()
        )
    else:
        return False


@click.command()
@click.argument(
    "tool-stats",
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
)
@click.argument(
    "outfile",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
)
def cli(tool_stats: Path, outfile: Path):
    """Get ecosyste.ms stats for all entries."""
    dotenv.load_dotenv()
    entries = pd.read_csv(tool_stats, index_col="id")
    if outfile.exists():
        existing_docs_df = pd.read_csv(outfile, index_col="id")
    else:
        existing_docs_df = pd.DataFrame()

    docs_df = pd.DataFrame(columns=COLS, index=entries.index)
    for id, entry in tqdm(entries.iterrows(), total=len(entries)):
        if id in existing_docs_df.index and existing_docs_df.loc[id].notnull().any():
            docs_df.loc[id] = existing_docs_df.loc[id]
        else:
            docs_df.loc[id] = pd.Series(_get_docs_data(entry.html_url))

    docs_df[COLS].sort_index().to_csv(outfile)


if __name__ == "__main__":
    cli()
