# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Get download trends for the repository packages."""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

import click
import pandas as pd
import util
from dateutil.relativedelta import relativedelta
from get_stats import _get_conda_download_df
from google.cloud import bigquery
from pandas import Series
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)
COLS = [
    "id",
    "html_url",
    "pypi_package_url",
    "pypi_package_name",
    "anaconda_package_url",
    "other_source",
]


def get_conda_download_trends(previous_months: int = 12) -> pd.DataFrame:
    """Retrieve conda package download statistics for the specified period.

    This function collects conda download data going back from the current month
    for a specified number of months. It validates that each month's data is
    within the expected date range and gracefully skips missing months.

    Parameters
    ----------
    previous_months : int, optional
        Number of months to retrieve download data for, going back from the
        current month. Default is 12.

    Returns:
    -------
    pd.DataFrame
        A concatenated DataFrame containing conda download statistics for all
        successfully retrieved months. The DataFrame includes a "time" column
        (in YYYY-MM format) and other download-related metrics.

    Raises:
    ------
    ValueError
        If the "time" column in the data for a given month contains more than
        one unique value (expected exactly one).

    Warnings:
    --------
    Logs a warning if a month's data falls outside the valid date range
    [min_month, max_month] or if data for a particular month cannot be found.
    """
    dfs = []

    now = datetime.now()
    # Current month in YYYY-MM format
    max_month = now.strftime("%Y-%m")
    # previous_months ago in YYYY-MM format
    min_month = (now - relativedelta(months=previous_months)).strftime("%Y-%m")

    for months_ago in range(1, previous_months + 1):
        try:
            df = _get_conda_download_df(months_ago=months_ago)

            # Check that time column contains only one unique value
            unique_months = df["time"].unique()
            if len(unique_months) != 1:
                raise ValueError(
                    f"Expected time column to have 1 unique value, but found {len(unique_months)}: {unique_months}"
                )
            df_month = unique_months[0]  # Get the single unique month
            if df_month < min_month or df_month > max_month:
                LOGGER.warning(
                    f"Month {df_month} is outside the valid range [{min_month}, {max_month}], stopping"
                )
                break
            dfs.append(df)
        except FileNotFoundError:
            LOGGER.warning(f"No conda download for month {months_ago}")
            continue

    previous_months_df = pd.concat(dfs, ignore_index=True)
    return previous_months_df


def find_conda_package(package_name: str) -> str | None:
    """Check if conda is installed and search for a package on Anaconda channels.

    Searches all specified channels simultaneously: conda-forge, bioconda, anaconda.
    Returns the package URL if found, None otherwise.

    Parameters
    ----------
    package_name : str
        The name of the package to search for

    Returns:
    -------
    Optional[str]
        The URL to the package if found, None if not found or conda is not installed
    """
    # Check if conda is installed
    try:
        result = subprocess.run(
            ["conda", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            print("Conda is not installed")
            return None
    except FileNotFoundError:
        print("Conda is not installed")
        return None
    except subprocess.TimeoutExpired:
        print("Conda check timed out")
        return None

    # Build command with multiple channels
    cmd = [
        "conda",
        "search",
        "--json",
        "--channel",
        "conda-forge",
        "--channel",
        "bioconda",
        "--channel",
        "anaconda",
        package_name,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        data = json.loads(result.stdout)

        # Check if response is empty or contains PackagesNotFoundError
        if not data or "PackagesNotFoundError" in data.get("exception_name", ""):
            LOGGER.warning(f"Package '{package_name}' not found in any channel")
            return None

        # Determine which channel the package came from
        # The first channel in the search list has priority
        url = f"https://anaconda.org/conda-forge/{package_name}"
        LOGGER.info(f"Package '{package_name}' found")
        return url

    except subprocess.TimeoutExpired:
        print("Conda search timed out")
        return None
    except json.JSONDecodeError:
        print("Error parsing conda response")
        return None
    except Exception as e:
        print(f"Error searching for package: {e}")
        return None


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
    ------------
    row : pandas.Series
        A row from a DataFrame.
    col : str
        The column name to check.

    Returns:
    --------
    bool
        True if the cell is non-null and contains non-whitespace content,
        False otherwise.
    """
    return bool(pd.notna(row[col]) and str(row[col]).strip() != "")


def skip_tool(
    row: pd.Series,
    months_back: int = 2,
    required_fields: list[str] = [
        "pypi_package_url",
        "pypi_package_name",
        "anaconda_package_url",
    ],
) -> bool:
    """Skip tool row if all required fields are populated.

    Determines whether to skip processing a tool row by checking if all
    required fields contain populated values. The required fields include
    a set of base fields plus dynamically generated month-based fields
    for the specified time period.

    Parameters
    ----------
    row : pd.Series
        A pandas Series representing a single row of data for a tool.
    months_back : int, default=2
        Number of months to generate in the past from the current date.
        Each month is formatted as "YYYY-MM" and added to the required fields.
    required_fields : list[str], default=["pypi_package_url", "pypi_package_name", "anaconda_package_url"]
        Base list of required field names that must be populated.

    Returns:
    -------
    bool
        True if all required fields (including month-based fields) are
        populated in the row, False otherwise.
    """
    months = (
        pd.date_range(end=pd.Timestamp.now(), periods=months_back, freq="MS")
        .strftime("%Y-%m")
        .tolist()
    )
    required_fields.extend(months)
    return all(_is_populated(row, field) for field in required_fields)


def query_file_downloads(
    package_name_list: list[str], bigquery_project_name: str = "openmod-tracker"
) -> pd.DataFrame:
    """Perform the BigQuery query to get the number of downloads for each package in the list over the past year, grouped by month and project.

    Parameters
    ------------
    package_name_list : list[str]
        List of package names to query.
    bigquery_project_name : str, optional
        The BigQuery project name, by default "openmod-tracker".

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


def get_conda_pkg_download_stats(list_of_packages: list[str]) -> pd.DataFrame:
    """Get conda download stats for a list of packages.

    Parameters
    ------------
    list_of_packages : list[str]
        List of package names to query.

    Returns:
    --------
    pd.DataFrame
        DataFrame containing the number of downloads for each package, grouped by month and project.
    """
    previous_months_df = get_conda_download_trends()
    filtered = previous_months_df[
        previous_months_df["pkg_name"]
        .str.casefold()
        .isin([pkg.casefold() for pkg in list_of_packages])
    ]
    grouped = filtered.groupby(["pkg_name", "time"])["counts"].sum().reset_index()
    wide = (
        grouped.pivot(index="pkg_name", columns="time", values="counts")
        .reset_index()
        .rename_axis(None, axis=1)
    )

    # Reorder columns: keep pkg_name first, then sort month columns in descending order
    time_columns = sorted(
        [col for col in wide.columns if col != "pkg_name"], reverse=True
    )
    wide = wide[["pkg_name"] + time_columns]

    return wide


def enrich_with_monthly_downloads(
    download_df: pd.DataFrame,
    pypi_download_stats_df: pd.DataFrame,
    conda_download_stats_df: pd.DataFrame,
) -> pd.DataFrame:
    """Add monthly download columns (wide format) to each tool row.

    Parameters
    ------------
    download_df : pd.DataFrame
        DataFrame containing the base download data.
    pypi_download_stats_df : pd.DataFrame
        DataFrame containing the monthly download statistics for pypi.
    conda_download_stats_df : pd.DataFrame
        DataFrame containing the monthly download statistics for anaconda..

    Returns:
    ---------
    pd.DataFrame
        DataFrame containing the monthly download statistics.
    """
    base = download_df.copy()
    pypi_stats = pypi_download_stats_df.copy()
    conda_stats = conda_download_stats_df.copy()

    # Keep original package names untouched; normalize only helper join keys
    base["_join_pkg"] = (
        base["pypi_package_name"].astype("string").str.casefold().str.strip()
    )
    pypi_stats["_join_pkg"] = (
        pypi_stats["project"].astype("string").str.casefold().str.strip()
    )
    conda_stats["_join_pkg"] = (
        conda_stats["pkg_name"].astype("string").str.casefold().str.strip()
    )

    pypi_stats["month"] = pd.to_datetime(pypi_stats["month"], errors="coerce")
    pypi_stats = pypi_stats.dropna(subset=["month", "_join_pkg"])
    pypi_stats["month_col"] = pypi_stats["month"].dt.strftime("%Y-%m")

    # Check whether some package-month appears more than once.
    # Potential duplicates would make the pivot fail.
    if pypi_stats.duplicated(subset=["_join_pkg", "month_col"], keep=False).any():
        raise ValueError(
            "Duplicate package-month rows found in download stats; expected unique pairs "
            "of (project, month)."
        )

    wide = pypi_stats.pivot(
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

        # Start from cached row if present, otherwise create a new one
        if tool_id in existing_by_id:
            existing_row = existing_by_id[tool_id]

            # If all the relevant columns are already populated, skip the tool to save time
            if skip_tool(existing_row):
                rows_out.append(existing_row.to_dict())
                continue
            # If some of the relevant columns are not populated, store the cached data
            row_data = existing_row.to_dict()
        else:
            row_data = {"id": tool_id, "html_url": row["html_url"]}

        # Preserve existing values. Only fill missing fields. Use .setdefault https://docs.python.org/3/library/stdtypes.html#dict.setdefault
        pypi_url, pypi_name = get_pypi_package_info(row["html_url"])
        if pypi_url and pypi_name:
            if "pypi" in pypi_url:
                row_data.setdefault("pypi_package_url", pypi_url)
                row_data.setdefault("pypi_package_name", pypi_name)
            else:
                row_data.setdefault("other_source", pypi_url)

        anaconda_package_url = find_conda_package(pypi_name) if pypi_name else None
        if anaconda_package_url:
            row_data.setdefault("anaconda_package_url", anaconda_package_url)

        rows_out.append(row_data)

    download_df = pd.DataFrame(rows_out, columns=COLS)
    package_name_list = list(download_df["pypi_package_name"].str.casefold().unique())

    if use_bigquery:
        # BigQuery is currently not enable for the GCP project compute-app
        pypi_download_stats_df = query_file_downloads(package_name_list)
    else:
        # Process a csv file with the queried data from the BigQuery Web UI
        pypi_download_stats_df = pd.read_csv(pypi_path)

    anaconda_download_stats_df = get_conda_pkg_download_stats(package_name_list)
    updated_df = enrich_with_monthly_downloads(
        download_df, pypi_download_stats_df, anaconda_download_stats_df
    )
    updated_df.to_csv(out_path, index=False)


if __name__ == "__main__":
    cli()
