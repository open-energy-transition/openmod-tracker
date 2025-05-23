import logging

import pandas as pd
from urlparse import parse

LOGGER = logging.getLogger(__file__)


def drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate data in the merged tool dataset.

    This will only consider normalised (lower case, no spaces) tool names when deciding whether there is a duplicate.

    Before dropping duplicates, any NaN data between sources will be used to fill NaNs where possible.

    Args:
        df (pd.DataFrame): Merged tool dataset.

    Returns:
        pd.DataFrame: `df` with identified duplicates dropped.
    """
    duplicates = df.set_index("id").index.duplicated()
    df_duplicates = df[duplicates]

    LOGGER.info(f"Found {len(duplicates)} duplicate entries")

    df_unique = df[~duplicates].set_index("id")
    for idx in df_duplicates.id.unique():
        dup_df = df_duplicates[df_duplicates["id"] == idx]
        sources = ",".join(dup_df.source.values)
        filled = df_unique.loc[[idx]]
        for _, series in dup_df.iterrows():
            with pd.option_context("future.no_silent_downcasting", True):
                filled = filled.fillna(value=series.dropna().to_dict())
        df_unique.loc[[idx]] = filled.assign(source=sources)
    return df_unique


def drop_no_git(df: pd.DataFrame) -> pd.DataFrame:
    """Only keep projects that define a git repo for their source code

    Args:
        df (pd.DataFrame): Project list

    Returns:
        pd.DataFrame: `df` without projects that do not define a git repo URL.
    """
    git_filter = df.url.apply(lambda x: "git" in parse.urlparse(x).netloc.lower())
    return df[git_filter]
