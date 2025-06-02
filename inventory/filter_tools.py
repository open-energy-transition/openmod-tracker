import logging
from urllib.parse import urlparse

import pandas as pd

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
        dup_df = df_duplicates[df_duplicates[on] == idx]
        sources = ",".join(set(dup_df.source.values))
        names = ",".join(set(dup_df.name.values))
        filled = df_unique.loc[[idx]]
        for _, series in dup_df.iterrows():
            with pd.option_context("future.no_silent_downcasting", True):
                filled = filled.fillna(value=series.dropna().to_dict())
        df_unique.loc[[idx]] = filled.assign(source=sources, name=names)
    return df_unique.reset_index()


def drop_no_git(df: pd.DataFrame) -> pd.DataFrame:
    """Only keep projects that define a git repo for their source code

    Args:
        df (pd.DataFrame): Project list

    Returns:
        pd.DataFrame: `df` without projects that do not define a git repo URL.
    """
    git_filter = df.url.apply(
        lambda x: pd.notnull(x) and "git" in urlparse(x).netloc.lower()
    )
    return df[git_filter]
