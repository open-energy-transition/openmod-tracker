# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Filter collected ESM tools to remove duplicates and non-Git source URLs."""

import difflib
import logging
from pathlib import Path
from urllib.parse import urlparse

import click
import pandas as pd
import requests
import util
from get_tools import TOOL_TYPES
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)
tqdm.pandas()


def drop_duplicates(df: pd.DataFrame, on: str = "url") -> pd.DataFrame:
    """Drop duplicate data in the merged tool dataset.

    This will only consider normalised (lower case, no spaces) tool names when deciding whether there is a duplicate.

    Before dropping duplicates, any NaN data between sources will be used to fill NaNs where possible.

    Args:
        df (pd.DataFrame): Merged tool dataset.
        on (str, optional): Column on which to check for duplicates. Defaults to "url".

    Returns:
        pd.DataFrame: `df` with identified duplicates dropped.
    """
    duplicates = df.set_index(on).index.duplicated()
    df_duplicates = df[duplicates]

    LOGGER.warning(
        f"Found {len(df_duplicates)} duplicate entries using the {on} column."
    )

    df_unique = df[~duplicates].set_index(on)

    for idx in df_duplicates[on].unique():
        dup_df = df[df[on] == idx]
        sources = ",".join(sorted(set(dup_df.source.values)))
        names = ",".join(sorted(set(dup_df.name.values)))
        filled = df_unique.loc[[idx]]
        best_id = _closest_id(idx, dup_df.id.unique())
        for _, series in dup_df.iterrows():
            with pd.option_context("future.no_silent_downcasting", True):
                filled = filled.fillna(value=series.dropna().to_dict())
        df_unique.loc[[idx]] = filled.assign(source=sources, name=names, id=best_id)
    return df_unique.reset_index()


def _closest_id(url: str, ids: list[str]) -> str:
    """Find the closest matching ID to a given URL from a list of IDs.

    Args:
        url (str): URL to match.
        ids (list[str]): List of IDs to search.

    Returns:
        str: Closest matching ID.
    """
    url_name = urlparse(url).path.lower().split("/")[-1]
    scores = {
        id_: difflib.SequenceMatcher(None, url_name, id_.lower()).ratio() for id_ in ids
    }
    best_id = max(scores, key=scores.get)
    return best_id


def drop_no_git(df: pd.DataFrame) -> pd.DataFrame:
    """Only keep projects that define a git repo for their source code.

    Args:
        df (pd.DataFrame): Project list

    Returns:
        pd.DataFrame: `df` without projects that do not define a git repo URL.
    """
    git_filter = df.url.apply(
        lambda x: (
            pd.notnull(x)
            and any(src in urlparse(x).netloc.lower() for src in ["git", "bitbucket"])
        )
    )
    new_df = df[git_filter]

    LOGGER.warning(
        f"Found {len(df) - len(new_df):d} entries without valid git repo URLs."
    )
    return new_df


def drop_exclusions(df: pd.DataFrame) -> pd.DataFrame:
    """Remove manually-derived exclusions from the tool list.

    Args:
        df (pd.DataFrame): ESM tool list.

    Returns:
        pd.DataFrame: Filtered `df`.
    """
    exclusions = pd.read_csv(Path(__file__).parent / "exclusions.csv")
    exclusion_filter = ~df.id.isin(exclusions.id)
    new_df = df[exclusion_filter]

    LOGGER.warning(
        f"Excluding {len(df) - len(new_df):d} entries following manual assessment."
    )
    return new_df


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


def resolve_duplicated_urls(df: pd.DataFrame) -> pd.DataFrame:
    """If there are duplicate Git URLs, they will need resolving by inspecting their ecosyste.ms entries.

    Args:
        df (pd.DataFrame): Tools table.

    Returns:
        pd.DataFrame: Tools table without duplicate IDs, choosing the most likely best URL option.
    """
    duplicate_cache = util.read_cache("duplicate_urls")
    duplicates = df[df.id.duplicated()]
    for duplicate in duplicates.id.unique():
        urls = df[df.id == duplicate].url
        LOGGER.warning(f"Found {len(urls)} entries for tool ID '{duplicate}'")
        if duplicate in duplicate_cache:
            url = duplicate_cache[duplicate]
            LOGGER.warning(f"Using cached resolved URL: {url}")
            df.loc[df.id == duplicate, "url"] = url
            continue
        for url in urls:
            repo_data = util.get_ecosystems_repo_data(url)
            if repo_data == "not-found":
                LOGGER.warning(f"Removing {url} as it has no ecosyste.ms entry.")
                df = df[df.url != url]
            elif repo_data is None:
                LOGGER.warning(
                    f"Removing {url} as we cannot access the ecosyste.ms server right now."
                )
                df = df[df.url != url]
            elif url != (new_url := repo_data["html_url"].lower()):
                LOGGER.warning(f"Found redirect for: {url} -> {new_url}.")
                df.loc[df.url == url, "url"] = new_url
            elif (new_name := repo_data["source_name"]) is not None:
                new_url = "https://" + urlparse(url).netloc + "/" + new_name.lower()
                LOGGER.warning(f"Removing {url} as it is a fork of {new_url}.")
                df.loc[df.url == url, "url"] = new_url
        remaining_urls = df[df.id == duplicate].url.unique()
        if len(remaining_urls) > 1:
            most_popular = (
                df[df.id == duplicate]
                .source.str.split(",", expand=True)
                .notnull()
                .sum(axis=1)
                .idxmax()
            )
            url = df.loc[most_popular, "url"]
            remaining_urls = [url]
            LOGGER.warning(
                f"Could not resolve duplicate URLs for {duplicate}. Remaining: {remaining_urls}. "
                f"Selecting the most popular option based on number of sources that list it: {url}."
            )

        duplicate_cache[duplicate] = remaining_urls[0]
    util.dump_cache("duplicate_urls", duplicate_cache)
    df = drop_duplicates(df, "url")
    return df


def _get_url(url_series: pd.Series) -> str | None:
    """Get the final URL for a repository, following redirects if necessary.

    Args:
        url_series (pd.Series): Series containing a single URL to check.

    Returns:
        str | None: The final URL after following redirects, or None if the URL is inaccessible.
    """
    # We expect only one unique URL per series.
    url = url_series.drop_duplicates().item()
    if pd.isnull(url):
        return None
    try:
        r = requests.get(url, allow_redirects=True, timeout=60)
        if r.ok:
            new_url = r.url.lower()
            if new_url != url:
                LOGGER.warning(f"Found redirect for: {url} -> {new_url}.")
            return new_url
        elif r.status_code == 443:
            LOGGER.warning(f"Read timed out for {url}, returning {url}.")
            return url
        else:
            LOGGER.warning(f"Error accessing {url}: {r.status_code}")
            return None
    except Exception as e:
        LOGGER.warning(f"Error accessing {url}: {e}")
        return None


@click.command()
@click.argument("infile", type=click.Path(exists=True, dir_okay=False, file_okay=True))
@click.argument(
    "outfile", type=click.Path(exists=False, dir_okay=False, file_okay=True)
)
@click.option(
    "--ignore",
    type=click.Choice(TOOL_TYPES),
    multiple=True,
    required=False,
    help="Ignore source of data as part of the filtering process.",
)
def cli(infile: Path, outfile: Path, ignore: tuple[str]):
    """Filter collated tool list."""
    entries = pd.read_csv(infile).drop("description", axis=1)
    entries_ignore_sources = entries[~entries["source"].isin(ignore)]

    redirected_urls = entries_ignore_sources.groupby("url").url.progress_apply(_get_url)
    entries_ignore_sources["url"] = entries_ignore_sources.url.map(redirected_urls)
    filtered_entries = entries_ignore_sources.dropna(subset=["url"])

    filtered_entries = drop_no_git(filtered_entries)

    filtered_entries = drop_duplicates(filtered_entries, on="url")
    filtered_entries = drop_exclusions(filtered_entries)
    filtered_entries = resolve_duplicated_urls(filtered_entries)

    # We fill any remaining gaps from the initial set of tools
    filler = drop_duplicates(entries_ignore_sources, on="id").set_index("id")
    reindexed_filler = filler.reindex(filtered_entries.set_index("id").index)
    filtered_entries = filtered_entries.set_index("id").fillna(
        {col: reindexed_filler[col] for col in reindexed_filler.columns}
    )

    filtered_entries.sort_index().to_csv(outfile)


if __name__ == "__main__":
    cli()
