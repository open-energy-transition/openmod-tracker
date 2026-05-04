# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Get download trends for the repository packages."""

from pathlib import Path

import click
import pandas as pd
import util
from pandas import Series
from tqdm import tqdm

COLS = ["id", "html_url", "pypi_package_url", "pypi_package_name","other_source"]


def get_pypi_package_info(url: str) -> tuple[str | None, str | None]:
    """Get the PyPI package URL from the repository URL.

    Parameters
    -----------
    url : str
        Repository URL.

    Returns:
    --------
    tuple[str | None, str | None]
        Tuple of (package_url, package_name), or (None, None) if not found.
    """
    packages = util.get_ecosystems_package_data(url)
    if packages:
        package = packages[0]
        registry_url = package["registry_url"].strip()
        if registry_url.endswith("/"):
            registry_url = registry_url[:-1]
        package_name = package["name"].strip()
        return registry_url, package_name
    return None, None


def _is_populated(row: Series, col: str) -> bool:
    """Check if a DataFrame cell is non-null and non-empty.

    Parameters
    ----------
    row : pandas.Series
        A row from a DataFrame.
    col : str
        The column name to check.

    Returns:
    -------
    bool
        True if the cell is non-null and contains non-whitespace content,
        False otherwise.
    """
    return bool(pd.notna(row[col]) and str(row[col]).strip() != "")


@click.command()
@click.option(
    "--stats-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to the CSV file containing repository URLs in the first column.",
    default="inventory/output/stats.csv",
)
@click.option(
    "--out-path",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
    help="Output path for the user interactions data file.",
    default="user_analysis/output/package_downloads.csv",
)
def cli(stats_file: Path, out_path: Path):
    """CLI entry point to collect all users who interact with repositories listed in a stats file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data into a dict for fast lookup
    existing_by_id = {}
    if out_path.exists():
        existing = pd.read_csv(out_path).drop_duplicates(subset=["id"], keep="last")
        existing_by_id = {row["id"]: row for _, row in existing.iterrows()}

    # Load stats
    stats_df = pd.read_csv(stats_file, usecols=["id", "html_url"])

    rows_out = []
    for _, row in tqdm(
        stats_df.iterrows(), total=len(stats_df), desc="Collecting package downloads"
    ):
        tool_id = row["id"]

        # Use cached data if complete
        if tool_id in existing_by_id:
            existing_row = existing_by_id[tool_id]
            if _is_populated(existing_row, "pypi_package_url") and _is_populated(
                existing_row, "pypi_package_name"
            ):
                rows_out.append(existing_row.to_dict())
                continue

        # Fetch missing data
        pypi_url, pypi_name = get_pypi_package_info(row["html_url"])
        rows_out.append(
            {
                "id": tool_id,
                "html_url": row["html_url"],
                "pypi_package_url": pypi_url,
                "pypi_package_name": pypi_name,
            }
        )

    pd.DataFrame(rows_out, columns=COLS).to_csv(out_path, index=False)


if __name__ == "__main__":
    cli()
