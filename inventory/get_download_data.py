# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Get download trends for the repository packages."""

from pathlib import Path

import click
import pandas as pd
import util
from google.cloud import bigquery
from pandas import Series
from tqdm import tqdm

COLS = ["id", "html_url", "pypi_package_url", "pypi_package_name", "other_source"]


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


def query_file_downloads(
    package_name_list: list[str], bigquery_project_name: str = "compute-app-427709 "
) -> pd.DataFrame:
    """Perform the BigQuery query to get the number of downloads for each package in the list over the past year, grouped by month and project.

    Parameters
    ------------
    package_name_list : list[str]
        List of package names to query.
    bigquery_project_name : str, optional
        The BigQuery project name, by default "compute-app-427709".

    Returns:
    --------
    pd.DataFrame
        DataFrame containing the number of downloads for each package, grouped by month and project.
    """
    # Create a BigQuery client
    client = bigquery.Client(project=bigquery_project_name)

    query = """
    SELECT
      COUNT(*) AS num_downloads,
      DATE_TRUNC(DATE(timestamp), MONTH) AS `month`,
      file.project AS `project`
    FROM `bigquery-public-data.pypi.file_downloads`
    WHERE
      details.ci is NULL
      AND DATE(timestamp)
        BETWEEN DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH)
        AND CURRENT_DATE()
      AND file.project IN UNNEST(@projects)
    GROUP BY `month`, `project`
    ORDER BY `month` DESC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("projects", "STRING", package_name_list)
        ]
    )
    query_job = client.query(query, job_config=job_config)
    df = query_job.to_dataframe()
    return df


def enrich_with_monthly_downloads(
    download_df: pd.DataFrame, download_stats_df: pd.DataFrame
) -> pd.DataFrame:
    """Add monthly download columns (wide format) to each tool row.

    Parameters
    ------------
    download_df : pd.DataFrame
        DataFrame containing the base download data.
    download_stats_df : pd.DataFrame
        DataFrame containing the monthly download statistics.

    Returns:
    ---------
    pd.DataFrame
        DataFrame containing the monthly download statistics.
    """
    base = download_df.copy()
    stats = download_stats_df.copy()

    # Keep original package names untouched; normalize only helper join keys
    base["_join_pkg"] = (
        base["pypi_package_name"].astype("string").str.casefold().str.strip()
    )
    stats["_join_pkg"] = stats["project"].astype("string").str.casefold().str.strip()

    stats["month"] = pd.to_datetime(stats["month"], errors="coerce")
    stats = stats.dropna(subset=["month", "_join_pkg"])
    stats["month_col"] = stats["month"].dt.strftime("%Y-%m")

    # Check whether some package-month appears more than once.
    # Potential duplicates would make the pivot fail.
    if stats.duplicated(subset=["_join_pkg", "month_col"], keep=False).any():
        raise ValueError(
            "Duplicate package-month rows found in download stats; expected unique pairs "
            "of (project, month)."
        )

    wide = stats.pivot(
        index="_join_pkg", columns="month_col", values="num_downloads"
    ).reset_index()

    month_cols = sorted([c for c in wide.columns if c != "_join_pkg"], reverse=True)
    wide = wide[["_join_pkg", *month_cols]]

    enriched = base.merge(wide, how="left", on="_join_pkg").drop(columns=["_join_pkg"])

    return enriched


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
@click.option(
    "--use_bigquery",
    type=bool,
    is_flag=True,
    default=False,
    help="Query BigQuery for the package downloads programmatically.",
)
@click.option(
    "--pypi-path",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
    help="Path to the CSV file containing the PyPI downloads per month and package..",
    default="inventory/output/pypi_downloads.csv",
)
def cli(stats_file: Path, out_path: Path, use_bigquery: bool, pypi_path: Path) -> None:
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

        row_data = {"id": tool_id, "html_url": row["html_url"]}

        if pypi_url and pypi_name:
            if "pypi" in pypi_url:
                row_data["pypi_package_url"] = pypi_url
                row_data["pypi_package_name"] = pypi_name
            else:
                row_data["other_source"] = pypi_url

        rows_out.append(row_data)

    download_df = pd.DataFrame(rows_out, columns=COLS)
    package_name_list = list(download_df["pypi_package_name"].str.casefold().unique())

    if use_bigquery:
        # BigQuery is currently not enable for the GCP project compute-app
        download_stats_df = query_file_downloads(package_name_list)
    else:
        # Process a csv file with the queried data from the BigQuery Web UI
        download_stats_df = pd.read_csv(pypi_path)

    updated_df = enrich_with_monthly_downloads(download_df, download_stats_df)

    updated_df.to_csv(out_path, index=False)


if __name__ == "__main__":
    cli()
