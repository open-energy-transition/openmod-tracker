"""Filter collected ESM tools to remove duplicates and non-Git source URLs."""

import logging
from pathlib import Path
from urllib.parse import urlparse

import click
import pandas as pd
from get_tools import TOOL_TYPES

LOGGER = logging.getLogger(__file__)


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
    entries = pd.read_csv(infile)
    entries_ignore_sources = entries.where(~entries["source"].isin(ignore)).dropna(
        how="all"
    )
    filtered_entries = drop_duplicates(entries_ignore_sources, on="id")
    filtered_entries = drop_duplicates(filtered_entries, on="url")
    filtered_entries = drop_no_git(filtered_entries)
    filtered_entries = drop_exclusions(filtered_entries)

    filtered_entries.sort_values("id").to_csv(outfile, index=False)


if __name__ == "__main__":
    cli()
