"""Get ecosyste.ms stats for defined projects."""

import logging
from pathlib import Path
from urllib.parse import urlparse

import click
import pandas as pd
import requests
import util
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)
COLS = ["rtd", "pages", "wiki"]
RTD_URL = "http://{slug}.readthedocs.io"


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
    for rtd_slug in [
        repo,
        repo.replace("_", "-"),
        f"{owner}-{repo}",
        f"{repo}-documentation",
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
    site_exists = _check_header(RTD_URL.format(slug=slug))
    if not site_exists:
        return False

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
    entries = pd.read_csv(tool_stats, index_col="id")
    if outfile.exists():
        existing_stats_df = pd.read_csv(outfile, index_col="id")
    else:
        existing_stats_df = pd.DataFrame()

    docs_df = pd.DataFrame(columns=COLS, index=entries.index)
    for id, entry in tqdm(entries.iterrows(), total=len(entries)):
        if existing_stats_df.get(id, pd.Series()).notnull().any():
            docs_df.loc[id] = existing_stats_df.loc[id]
        else:
            docs_df.loc[id] = pd.Series(_get_docs_data(entry.html_url))

    docs_df[COLS].sort_index().to_csv(outfile)


if __name__ == "__main__":
    cli()
