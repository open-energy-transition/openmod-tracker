"""Filter collected ESM tools to remove duplicates and non-Git source URLs."""

import logging
from pathlib import Path
from urllib.parse import urlparse

import click
import pandas as pd
import util
from get_tools import TOOL_TYPES

LOGGER = logging.getLogger(__name__)


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
        for _, series in dup_df.iterrows():
            with pd.option_context("future.no_silent_downcasting", True):
                filled = filled.fillna(value=series.dropna().to_dict())
        df_unique.loc[[idx]] = filled.assign(source=sources, name=names)
    return df_unique.reset_index()


def drop_no_git(df: pd.DataFrame) -> pd.DataFrame:
    """Only keep projects that define a git repo for their source code.

    Args:
        df (pd.DataFrame): Project list

    Returns:
        pd.DataFrame: `df` without projects that do not define a git repo URL.
    """
    git_filter = df.url.apply(
        lambda x: pd.notnull(x)
        and any(src in urlparse(x).netloc.lower() for src in ["git", "bitbucket"])
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
    duplicates = df[df.id.duplicated()]
    for duplicate in duplicates.id.unique():
        urls = df[df.id == duplicate].url
        LOGGER.warning(f"Found {len(urls)} entries for tool ID '{duplicate}'")
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
                df.loc[df.id == duplicate, "url"] = new_url
            elif (new_name := repo_data["source_name"]) is not None:
                new_url = "https://" + urlparse(url).netloc + "/" + new_name.lower()
                LOGGER.warning(f"Removing {url} as it is a fork of {new_url}.")
                df.loc[df.id == duplicate, "url"] = new_url
        remaining_urls = df[df.id == duplicate].url.unique()
        if len(remaining_urls) > 1:
            LOGGER.warning(
                f"Could not resolve duplicate URLs for {duplicate}. Remaining: {remaining_urls}."
            )
    df = drop_duplicates(df, "url")
    return df


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
    filtered_entries = drop_no_git(entries_ignore_sources)
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
