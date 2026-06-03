# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Get download trends for the repository packages."""

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
    "juliahub_package_url",
    "other_source",
]
ECOSYSTEM_URL_PATTERNS = {
    "pypi": "https://pypi.org/project/",
    "conda": "https://anaconda.org/",
    "julia": "https://juliahub.com/",
}


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


def is_conda_installed() -> bool:
    """Check if Conda is installed and accessible.

    This function attempts to run the `conda --version` command to verify
    that Conda is installed and available on the system PATH.

    Returns:
    -------
    bool
        True if Conda is installed and accessible, False otherwise.

    Notes:
    -----
    If Conda is not found or the check times out (5 seconds), a warning
    is logged and False is returned.
    """
    try:
        result = subprocess.run(
            ["conda", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        LOGGER.warning("Conda is not installed or check timed out")
        return False


def clean_url(url_str: str) -> str:
    """Remove whitespace and trailing slashes from a URL string.

    Parameters
    ----------
    url_str : str
        The URL string to clean.

    Returns:
    -------
    str
        The cleaned URL string with leading/trailing whitespace and trailing slashes removed.
    """
    return url_str.strip().rstrip("/")


def select_package_info(packages: list[dict], ecosystem: str) -> dict | None:
    """Select the best package for a given ecosystem.

    If multiple packages exist for the same ecosystem, prefer the one with
    a populated registry_url matching the expected pattern for that ecosystem.
    As an example consider the response body of the GET call
    https://packages.ecosyste.ms/api/v1/packages/lookup?repository_url=https%3A%2F%2Fgithub.com%2FCURENT%2Fandes, which contains two
    packages for the "pypi" ecosystem, but only one of them has a valid registry_url starting with "https://pypi.org/project/".

    Parameters
    ------------
    packages : list[dict]
        List of package dictionaries, each containing at least an "ecosystem" key and optionally a "registry_url".
    ecosystem : str
        The ecosystem to filter packages by (e.g., "pypi", "conda", "julia").

    Returns:
    --------
    dict | None:
        The selected package dictionary for the specified ecosystem, or None if no matching package is found.
    """
    matching_packages = [pkg for pkg in packages if pkg["ecosystem"] == ecosystem]

    if not matching_packages:
        LOGGER.warning("No packages found for ecosystem %s", ecosystem)
        return None

    if len(matching_packages) == 1:
        return matching_packages[0]

    LOGGER.warning("Multiple packages found for ecosystem %s", ecosystem)
    pattern = ECOSYSTEM_URL_PATTERNS.get(ecosystem)

    # Find a package with valid registry_url
    pkg = next(
        (
            p
            for p in matching_packages
            if p.get("registry_url")
            and clean_url(p["registry_url"]).startswith(pattern)
        ),
        None,
    )

    if not pkg:
        LOGGER.warning(
            "No packages with a valid registry_url found for ecosystem %s", ecosystem
        )

    return pkg


def pick_cached_or_current(row: pd.Series, current: str | None, col: str) -> str | None:
    """Return current value if populated, otherwise fall back to cache.

    Parameters
    ----------
    row : pd.Series
        Row from the cache DataFrame.
    current : str | None
        Currently fetched value (may be None).
    col : str
        Column name in the cache row to check.

    Returns:
    -------
    str | None
        The current value if not None, otherwise the cached value if populated, otherwise None.
    """
    # If we have a current value, use it
    if current is not None:
        return current

    # Otherwise, try to use the cached value if it's populated
    if pd.notna(row[col]) and str(row[col]).strip() != "":
        return row[col]

    # No current value and no cached value
    return None


def use_package_info_cache(
    url: str,
    pypi_url: str | None,
    conda_url: str | None,
    julia_url: str | None,
    other_url: str | None,
    pypi_pkg_name: str | None,
    manual_cache_path: Path,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Enrich package info with values from a manual cache CSV, filling only None fields.

    This function looks up the repository URL in a manual cache CSV file and uses
    cached values to fill in any missing (None) package information. Current values
    normally take precedence over cached values, except for specific URLs that require
    cache override.

    Parameters
    ----------
    url : str
        Repository URL to look up in the cache.
    pypi_url : str | None
        Currently fetched PyPI package URL.
    conda_url : str | None
        Currently fetched Conda package URL.
    julia_url : str | None
        Currently fetched Julia package URL.
    other_url : str | None
        Currently fetched other ecosystem URL.
    pypi_pkg_name : str | None
        Currently fetched PyPI package name.
    manual_cache_path : Path
        Path to the CSV file containing cached package information.

    Returns:
    -------
    tuple[str | None, str | None, str | None, str | None, str | None]
        Tuple of (pypi_url, conda_url, julia_url, other_url, pypi_pkg_name) with
        current values taking precedence, falling back to cached values when current is None.
        For specific URLs, cached values always take precedence.
    """
    # Special case: URLs that should always use cache values
    FORCE_CACHE_URLS = {
        "https://github.com/RoseauTechnologies/Roseau_Load_Flow".casefold()
    }

    force_cache = url.casefold() in FORCE_CACHE_URLS

    # If all current values are already populated and we're not forcing cache, no need to check cache
    all_populated = all(
        val is not None
        for val in [pypi_url, conda_url, julia_url, other_url, pypi_pkg_name]
    )
    if all_populated and not force_cache:
        return pypi_url, conda_url, julia_url, other_url, pypi_pkg_name

    # Try to load the cache file
    try:
        manual_cache_df = pd.read_csv(manual_cache_path)
    except FileNotFoundError:
        LOGGER.warning(f"Manual cache not found: {manual_cache_path}")
        return pypi_url, conda_url, julia_url, other_url, pypi_pkg_name

    # Look for a matching row in the cache
    match = manual_cache_df[
        manual_cache_df["html_url"].str.casefold() == url.casefold()
    ]

    if match.empty:
        # No cache entry for this URL
        return pypi_url, conda_url, julia_url, other_url, pypi_pkg_name

    # Use the first matching row to fill in missing values
    row = match.iloc[0]

    # If forcing cache, return cache values directly (ignoring current values)
    if force_cache:
        LOGGER.info(f"Forcing cache values for {url}")
        return (
            row["pypi_package_url"]
            if pd.notna(row["pypi_package_url"])
            and str(row["pypi_package_url"]).strip() != ""
            else pypi_url,
            row["anaconda_package_url"]
            if pd.notna(row["anaconda_package_url"])
            and str(row["anaconda_package_url"]).strip() != ""
            else conda_url,
            row["juliahub_package_url"]
            if pd.notna(row["juliahub_package_url"])
            and str(row["juliahub_package_url"]).strip() != ""
            else julia_url,
            row["other_source"]
            if pd.notna(row["other_source"]) and str(row["other_source"]).strip() != ""
            else other_url,
            row["pypi_package_name"]
            if pd.notna(row["pypi_package_name"])
            and str(row["pypi_package_name"]).strip() != ""
            else pypi_pkg_name,
        )

    # Normal case: current values take precedence, cache fills in gaps
    return (
        pick_cached_or_current(row, pypi_url, "pypi_package_url"),
        pick_cached_or_current(row, conda_url, "anaconda_package_url"),
        pick_cached_or_current(row, julia_url, "juliahub_package_url"),
        pick_cached_or_current(row, other_url, "other_source"),
        pick_cached_or_current(row, pypi_pkg_name, "pypi_package_name"),
    )


def get_package_info(
    url: str, manual_cache: Path, known_ecosystems: set[str] | None = None
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Get the package URL and name for PyPI, Anaconda, JuliaHub, and others from repository URL.

    This function queries the ecosyste.ms API for package information and falls back
    to a manual cache for missing values. It extracts package URLs and names for
    known ecosystems (PyPI, Conda, Julia) and identifies any other ecosystems.

    Parameters
    ----------
    url : str
        Repository URL to look up.
    manual_cache : Path
        Path to the CSV file containing cached package information.
    known_ecosystems : set[str] | None
        Set of ecosystem names to exclude from "other_url". Defaults to {"julia", "conda", "pypi"}.

    Returns:
    -------
    tuple[str | None, str | None, str | None, str | None, str | None]
        Tuple of (pypi_url, conda_url, julia_url, other_url, pypi_pkg_name).
    """
    if known_ecosystems is None:
        known_ecosystems = {"julia", "conda", "pypi"}

    pypi_url = None
    conda_url = None
    julia_url = None
    other_url = None
    pypi_pkg_name = None

    # Try to fetch package data from ecosyste.ms API
    try:
        packages = util.get_ecosystems_package_data(url)
    except Exception as e:
        LOGGER.error(f"Failed to fetch package data for {url}: {e}")
        packages = None

    # Extract package info if available
    if packages:
        # Extract package info for known ecosystems
        pypi_pkg = select_package_info(packages, "pypi")
        conda_pkg = select_package_info(packages, "conda")
        julia_pkg = select_package_info(packages, "julia")

        pypi_url = clean_url(pypi_pkg["registry_url"]) if pypi_pkg else None
        conda_url = clean_url(conda_pkg["registry_url"]) if conda_pkg else None
        julia_url = clean_url(julia_pkg["registry_url"]) if julia_pkg else None
        pypi_pkg_name = pypi_pkg.get("name", "").strip() if pypi_pkg else None

        # Find first "other" ecosystem (not in known_ecosystems)
        other_url = next(
            (
                clean_url(pkg["registry_url"])
                for pkg in packages
                if pkg["ecosystem"] not in known_ecosystems and pkg.get("registry_url")
            ),
            None,
        )

        if other_url:
            other_ecosystem = next(
                pkg["ecosystem"]
                for pkg in packages
                if pkg["ecosystem"] not in known_ecosystems and pkg.get("registry_url")
            )
            LOGGER.info(f"Found other ecosystem for {url}: {other_ecosystem}")

    # Fill in any missing values from manual cache
    (
        enriched_pypi_url,
        enriched_conda_url,
        enriched_julia_url,
        enriched_other_url,
        enriched_pypi_pkg_name,
    ) = use_package_info_cache(
        url, pypi_url, conda_url, julia_url, other_url, pypi_pkg_name, manual_cache
    )

    return (
        enriched_pypi_url,
        enriched_conda_url,
        enriched_julia_url,
        enriched_other_url,
        enriched_pypi_pkg_name,
    )


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


def use_cache(
    row: pd.Series,
    months_back: int = 2,
    required_fields: list[str] = [
        "pypi_package_url",
        "pypi_package_name",
        "anaconda_package_url",
        "juliahub_package_url",
    ],
) -> bool:
    """Use cached row if all required fields are populated.

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
    required_fields : list[str], default=["pypi_package_url", "pypi_package_name", "anaconda_package_url", "juliahub_package_url"]
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
    return grouped


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
        DataFrame containing the monthly download statistics for anaconda.

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

    pypi_stats["month"] = pd.to_datetime(
        pypi_stats["month"], errors="coerce"
    ).dt.strftime("%Y-%m")
    pypi_stats["num_downloads"] = pd.to_numeric(
        pypi_stats["num_downloads"], errors="coerce"
    )
    pypi_stats = pypi_stats[["_join_pkg", "month", "num_downloads"]].dropna()

    conda_stats["month"] = pd.to_datetime(
        conda_stats["time"], errors="coerce"
    ).dt.strftime("%Y-%m")
    conda_stats["num_downloads"] = pd.to_numeric(conda_stats["counts"], errors="coerce")
    conda_stats = conda_stats[["_join_pkg", "month", "num_downloads"]].dropna()

    # Check whether some package-month appears more than once.
    # Potential duplicates would make the pivot fail.
    if pypi_stats.duplicated(subset=["_join_pkg", "month"], keep=False).any():
        raise ValueError(
            "Duplicate _join_pkg-month rows found in the PyPI download stats; expected unique pairs."
        )

    # Check whether some package-month appears more than once.
    # Potential duplicates would make the pivot fail.
    if conda_stats.duplicated(subset=["_join_pkg", "month"], keep=False).any():
        raise ValueError(
            "Duplicate _join_pkg-month rows found in the Anaconda download stats; expected unique pairs."
        )

    # Combine both sources and pivot
    combined = pd.concat([pypi_stats, conda_stats], ignore_index=True).dropna()
    monthly = (
        combined.groupby(["_join_pkg", "month"])["num_downloads"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    month_cols = sorted([c for c in monthly.columns if c != "_join_pkg"], reverse=True)
    monthly = monthly[["_join_pkg", *month_cols]]

    # Merge back to base
    return base.merge(monthly, how="left", on="_join_pkg").drop(columns=["_join_pkg"])


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
@click.option(
    "--package-cache-path",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
    help="Path to the CSV file containing the Package information.",
    default="inventory/manual_cache/package_urls_manual_search.csv",
)
def cli(
    stats_file: Path,
    out_path: Path,
    use_bigquery: bool,
    pypi_path: Path,
    package_cache_path: Path,
) -> None:
    """CLI entry point to collect all users who interact with repositories listed in a stats file."""
    is_conda_available = is_conda_installed()
    if not is_conda_available:
        raise SystemExit(
            "Conda is not installed or not accessible. Please install conda and try again."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data into a dict for fast lookup
    # existing_by_id = {}
    # if out_path.exists():
    #    #existing = pd.read_csv(out_path).drop_duplicates(subset=["id"], keep="last")
    #    # existing_by_id = {row["id"]: row for _, row in existing.iterrows()}

    # Load stats
    stats_df = pd.read_csv(stats_file, usecols=["id", "html_url"])
    # repo_to_pkg_df = pd.read_csv("user_analysis/output/repo_to_package.csv")

    rows_out = []
    for _, row in tqdm(
        stats_df.iterrows(), total=len(stats_df), desc="Collecting package downloads"
    ):
        tool_id = row["id"]

        # # Start from cached row if present, otherwise create a new one
        # if tool_id in existing_by_id:
        #     existing_row = existing_by_id[tool_id]
        #
        #     # If all the relevant columns are already populated, skip the tool to save time
        #     if use_cache(existing_row):
        #         rows_out.append(existing_row.to_dict())
        #         continue
        #     # If some of the relevant columns are not populated, store the cached data
        #     row_data = existing_row.to_dict()
        # else:
        #     row_data = {"id": tool_id, "html_url": row["html_url"]}

        row_data = {"id": tool_id, "html_url": row["html_url"]}

        # Preserve existing values. Only fill missing fields. Use .setdefault https://docs.python.org/3/library/stdtypes.html#dict.setdefault
        pypi_pkg_url, conda_pkg_url, julia_pkg_url, other_pkg_url, pypi_pkg_name = (
            get_package_info(row["html_url"], package_cache_path)
        )
        row_data.setdefault("pypi_package_url", pypi_pkg_url)
        row_data.setdefault("pypi_package_name", pypi_pkg_name)
        row_data.setdefault("anaconda_package_url", conda_pkg_url)
        row_data.setdefault("juliahub_package_url", julia_pkg_url)
        row_data.setdefault("other_source", other_pkg_url)

        rows_out.append(row_data)

    download_df = pd.DataFrame(rows_out, columns=COLS)
    package_name_list = list(
        download_df["pypi_package_name"].dropna().str.casefold().unique()
    )

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
