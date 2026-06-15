# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Get download trends for the repository packages."""

import logging
from dataclasses import dataclass
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

ECOSYSTEM_URL_PATTERNS = {
    "pypi": "https://pypi.org/project/",
    "conda": "https://anaconda.org/",
    "julia": "https://juliahub.com/",
}
LOGGER = logging.getLogger(__name__)
PACKAGE_INFO_ATTRS = [
    "pypi_package_url",
    "pypi_package_name",
    "anaconda_package_url",
    "juliahub_package_url",
    "other_source",
]
PACKAGE_INFO_COLUMNS = ["id", "html_url"] + PACKAGE_INFO_ATTRS


@dataclass
class PackageInfo:
    """Package information from various package managers and registries.

    Stores URLs and names for a package across different ecosystems.
    Each field is optional (None) if the package is not available in
    that particular package manager or registry.

    Attributes:
        pypi_package_url (str | None): URL to the package on PyPI (Python Package Index).
            Example: "https://pypi.org/project/requests/"
        pypi_package_name (str | None): Name of the package as registered on PyPI.
            Example: "requests"
        anaconda_package_url (str | None): URL to the package on Anaconda/Conda repository.
            Example: "https://anaconda.org/conda-forge/numpy"
        juliahub_package_url (str | None): URL to the package on JuliaHub (Julia package registry).
            Example: "https://juliahub.com/ui/Packages/Plots/..."
        other_source (str | None): URL to alternative package source or registry.
            Used for packages hosted outside major registries.
    """

    pypi_package_url: str | None
    pypi_package_name: str | None
    anaconda_package_url: str | None
    juliahub_package_url: str | None
    other_source: str | None


def get_conda_download_trends(previous_months: int) -> pd.DataFrame:
    """Retrieve conda package download statistics for the specified period.

    This function collects conda download data going back from the current month
    for a specified number of months. It validates that each month's data is
    within the expected date range and gracefully skips missing months.

    Args:
        previous_months (int): Number of months to retrieve download data for, going back from the
            current month.

    Returns:
        pd.DataFrame: A concatenated DataFrame containing conda download statistics for all
            successfully retrieved months. The DataFrame includes a "time" column
            (in YYYY-MM format) and other download-related metrics.

    Raises:
        ValueError: If the "time" column in the data for a given month contains more than
            one unique value (expected exactly one).

    Warnings:
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


def clean_url(url_str: str) -> str:
    """Remove whitespace and trailing slashes from a URL string.

    Args:
        url_str (str): The URL string to clean.

    Returns:
        str: The cleaned URL string with leading/trailing whitespace and trailing slashes removed.
    """
    return url_str.strip().rstrip("/")


def select_package_info(packages: list[dict], ecosystem: str) -> dict | None:
    """Select the best package for a given ecosystem.

    If multiple packages exist for the same ecosystem, prefer the one with
    a populated registry_url matching the expected pattern for that ecosystem.
    As an example consider the response body of the GET call
    https://packages.ecosyste.ms/api/v1/packages/lookup?repository_url=https%3A%2F%2Fgithub.com%2FCURENT%2Fandes, which contains two
    packages for the "pypi" ecosystem, but only one of them has a valid registry_url starting with "https://pypi.org/project/".

    Args:
        packages (list[dict]): List of package dictionaries, each containing at least an "ecosystem" key and optionally a "registry_url".
        ecosystem (str): The ecosystem to filter packages by (e.g., "pypi", "conda", "julia").

    Returns:
        dict | None: The selected package dictionary for the specified ecosystem, or None if no matching package is found.
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

    Args:
        row (pd.Series): Row from the cache DataFrame.
        current (str | None): Currently fetched value (may be None).
        col (str): Column name in the cache row to check.

    Returns:
        str | None: The current value if not None, otherwise the cached value if populated, otherwise None.
    """
    # If we have a current value, use it
    if current is not None:
        return current

    # Otherwise, try to use the cached value if it's populated
    if pd.notna(row[col]) and str(row[col]).strip() != "":
        return row[col]

    # No current value and no cached value
    return None


def enrich_package_info_from_cache(
    url: str, package_info: PackageInfo, manual_cache_path: Path
) -> PackageInfo:
    """Enrich package info with values from a manual cache CSV, filling only None fields.

    This function looks up the repository URL in a manual cache CSV file and uses
    cached values to fill in any missing (None) package information. Current values
    normally take precedence over cached values, except for specific URLs that require
    cache override.

    Args:
        url (str): Repository URL to look up in the cache.
        package_info (PackageInfo): Currently fetched package information.
        manual_cache_path (Path): Path to the CSV file containing cached package information.

    Returns:
        PackageInfo: Object with current values taking precedence, falling back to
            cached values when current is None. For specific URLs, cached values always take precedence.
    """
    # Special case: URL that should always use cache values.
    # As explained in https://github.com/open-energy-transition/openmod-tracker/issues/125#issuecomment-4610376320,
    # the response from the ecosystem package API contains two pypi packages urls
    # https://pypi.org/project/roseau-load-flow-engine/ and https://pypi.org/project/roseau-load-flow/.
    # The first package redirects to the second.
    # Hence, we force the tool to use the cached value https://pypi.org/project/roseau-load-flow,roseau-load-flow.
    # For RHEIA, the ecosystem package API response contains two pypi packages urls
    # https://pypi.org/project/rheia-meca2675 and https://pypi.org/project/rheia. Given the fact that the latter has no download data,
    # we keep the former.

    # Try to load the cache file
    try:
        manual_cache_df = pd.read_csv(
            manual_cache_path, dtype={"force_overwrite": bool}
        )
    except FileNotFoundError:
        LOGGER.warning(f"Manual cache not found: {manual_cache_path}")
        return package_info

    # Look for a matching row in the cache
    match = manual_cache_df[
        manual_cache_df["html_url"].str.casefold() == url.casefold()
    ]

    if match.empty:
        # No cache entry for this URL
        return package_info

    # Use the first matching row to fill in missing values
    row = match.iloc[0]

    # If all current values are already populated, and we are not forcing cache, no need to check cache
    all_populated = all(
        val is not None
        for val in [
            package_info.pypi_package_url,
            package_info.anaconda_package_url,
            package_info.juliahub_package_url,
            package_info.other_source,
            package_info.pypi_package_name,
        ]
    )
    if all_populated and not row["force_overwrite"]:
        return package_info

    # If forcing cache, return cache values directly (ignoring current values)
    if row["force_overwrite"]:
        LOGGER.info(f"Forcing cache values for {url}")
        return PackageInfo(
            **{
                attr: (
                    row[attr]
                    if pd.notna(row[attr]) and str(row[attr]).strip() != ""
                    else getattr(package_info, attr)
                )
                for attr in PACKAGE_INFO_ATTRS
            }
        )

    # Normal case: current values take precedence, cache fills in gaps
    return PackageInfo(
        **{
            attr: pick_cached_or_current(row, getattr(package_info, attr), attr)
            for attr in PACKAGE_INFO_ATTRS
        }
    )


def get_tool_info(
    url: str, manual_cache: Path, known_ecosystems: set[str] | None = None
) -> PackageInfo:
    """Get the package URL and name for PyPI, Anaconda, JuliaHub, and others from the repository URL.

    This function queries the ecosyste.ms API for package information and falls back
    to a manual cache for missing values. It extracts package URLs and names for
    known ecosystems (PyPI, Conda, Julia) and identifies any other ecosystems.

    Args:
        url (str): Repository URL to look up.
        manual_cache (Path): Path to the CSV file containing cached package information.
        known_ecosystems (set[str] | None): Set of ecosystem names to exclude from "other_url". Defaults to {"julia", "conda", "pypi"}.

    Returns:
        PackageInfo: PackageInfo object containing package URLs and PyPI package name.
    """
    if known_ecosystems is None:
        known_ecosystems = set(ECOSYSTEM_URL_PATTERNS.keys())

    pypi_url = None
    conda_url = None
    julia_url = None
    other_url = None
    pypi_pkg_name = None

    # Try to fetch package data from ecosyste.ms package API
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
        other_pkg = next(
            (
                pkg
                for pkg in packages
                if pkg["ecosystem"] not in known_ecosystems and pkg.get("registry_url")
            ),
            None,
        )

        if other_pkg:
            other_url = clean_url(other_pkg["registry_url"])
            LOGGER.info(f"Found other ecosystem for {url}: {other_pkg['ecosystem']}")

    # Fill in any missing values from manual cache
    package_info = PackageInfo(
        pypi_package_url=pypi_url,
        pypi_package_name=pypi_pkg_name,
        anaconda_package_url=conda_url,
        juliahub_package_url=julia_url,
        other_source=other_url,
    )
    return enrich_package_info_from_cache(url, package_info, manual_cache)


def _is_populated(row: Series, col: str) -> bool:
    """Check if a DataFrame cell is non-null and non-empty.

    Args:
        row (pandas.Series): A row from a DataFrame.
        col (str): The column name to check.

    Returns:
        bool: True if the cell is non-null and contains non-whitespace content,
            False otherwise.
    """
    return bool(pd.notna(row[col]) and str(row[col]).strip() != "")


def should_skip_fetching(row: pd.Series) -> bool:
    """Use cached row if all required fields are populated based on package type.

    Determines whether to skip processing a tool row by checking if all
    required fields contain populated values. The required fields vary based
    on the package type.

    Package type determination follows this priority:

    1. Julia packages: If html_url contains ".jl", required fields are
       id, html_url, juliahub_package_url.
    2. Other source packages: If other_source is populated, required fields are
       id, html_url, other_source.
    3. PyPI packages: If pypi_package_name is populated, required fields are
       id, html_url, pypi_package_url, pypi_package_name.

    If none of these conditions are met, the row is not considered cacheable.

    Args:
        row (pd.Series): A pandas Series representing a single row of data for a tool.

    Returns:
        bool: True if all required fields for the package type are populated in the
            row, False otherwise.
    """
    # Determine required fields based on package type
    base_fields = ["id", "html_url"]

    # Check if it's a Julia package
    if _is_populated(row, "html_url") and ".jl" in str(row["html_url"]):
        required_fields = base_fields + ["juliahub_package_url"]
    # Check if other_source is populated
    elif _is_populated(row, "other_source"):
        required_fields = base_fields + ["other_source"]
    # Check if pypi_package_name is populated
    elif _is_populated(row, "pypi_package_name"):
        required_fields = base_fields + ["pypi_package_url", "pypi_package_name"]
    else:
        # None of the package types matched
        return False

    # Check if all required fields are populated
    return all(_is_populated(row, field) for field in required_fields)


def get_package_info(
    statistics_df: pd.DataFrame,
    manual_cache_path: Path,
    cached_package_info_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Collect package information for tools from various package managers.

    This function retrieves package URLs and names from PyPI, Conda, Julia, and other
    package sources for tools listed in the input DataFrame. It implements a caching
    mechanism to avoid re-fetching data that has already been collected. Existing
    cached data is preserved and only missing fields are populated.

    Args:
        statistics_df (pd.DataFrame): DataFrame containing tool statistics with at least the following columns:
            - id : unique tool identifier
            - html_url : URL to the tool's repository or homepage
        manual_cache_path (Path): Path to the directory containing manual cache data used by get_tool_info()
            to speed up package lookups.
        cached_package_info_df (pd.DataFrame | None): Previously cached package information (only PACKAGE_INFO_COLUMNS).
            If None, all package info will be fetched fresh.

    Returns:
        pd.DataFrame: DataFrame with package information for all tools, containing columns
            specified in PACKAGE_INFO_COLUMNS. Includes:

            - id : tool identifier
            - html_url : original tool URL
            - pypi_package_url : URL to PyPI package page (if available)
            - pypi_package_name : name of PyPI package (if available)
            - anaconda_package_url : URL to Conda package page (if available)
            - juliahub_package_url : URL to Julia package page (if available)
            - other_source : URL to alternative package sources (if available)
    """
    # Load existing data into a dict for fast lookup
    existing_by_id = {}
    if cached_package_info_df is not None and not cached_package_info_df.empty:
        existing = cached_package_info_df.drop_duplicates(subset=["id"], keep="last")
        existing_by_id = {row["id"]: row for _, row in existing.iterrows()}

    rows_out = []
    for _, row in tqdm(
        statistics_df.iterrows(),
        total=len(statistics_df),
        desc="Collecting package information",
    ):
        tool_id = row["id"]

        # Start from cached row if present, otherwise create a new one
        if tool_id in existing_by_id:
            existing_row = existing_by_id[tool_id]

            # If all the relevant columns are already populated, skip the tool to save time and resources
            if should_skip_fetching(existing_row):
                rows_out.append(existing_row.to_dict())
                continue
            # If some of the relevant columns are not populated, store the cached data
            # It could be in fact that one of the relevant columns becomes available on the ecosystem package API
            # in the future. Hence, we should retain the possibility of fetching this piece of information in the future
            row_data = existing_row.to_dict()
        else:
            row_data = {"id": tool_id, "html_url": row["html_url"]}

        # Preserve existing values. Only fill missing fields. Use .setdefault https://docs.python.org/3/library/stdtypes.html#dict.setdefault
        pkg_info = get_tool_info(row["html_url"], manual_cache_path)
        row_data.setdefault("pypi_package_url", pkg_info.pypi_package_url)
        row_data.setdefault("pypi_package_name", pkg_info.pypi_package_name)
        row_data.setdefault("anaconda_package_url", pkg_info.anaconda_package_url)
        row_data.setdefault("juliahub_package_url", pkg_info.juliahub_package_url)
        row_data.setdefault("other_source", pkg_info.other_source)

        rows_out.append(row_data)

    return pd.DataFrame(rows_out, columns=PACKAGE_INFO_COLUMNS)


def get_expected_month_columns(months_back: int) -> list[str]:
    """Get list of expected month column names for the last months_back months.

    Args:
        months_back (int): Number of months to look back from current date.

    Returns:
        list[str]: List of month column names in YYYY-MM format, sorted descending.
    """
    end_date = pd.Timestamp.now() - pd.DateOffset(months=1)
    months = (
        pd.date_range(end=end_date, periods=months_back, freq="MS")
        .strftime("%Y-%m")
        .tolist()
    )
    return sorted(months, reverse=True)


def query_file_downloads(
    package_name_list: list[str],
    months_back: int,
    bigquery_project_name: str = "openmod-tracker",
) -> pd.DataFrame:
    """Perform the BigQuery query to get the number of downloads for each package over a specified period, grouped by month and project.

    Args:
        package_name_list (list[str]): List of package names to query.
        months_back (int): Number of months to look back.
        bigquery_project_name (str): The BigQuery project name, by default "openmod-tracker".

    Returns:
        pd.DataFrame: DataFrame containing the number of downloads for each package, grouped by month and project.
    """
    # Validate and sanitize months_back
    try:
        months_back = int(months_back)
    except (ValueError, TypeError):
        raise ValueError("months_back must be an integer")

    if months_back <= 0:
        raise ValueError("months_back must be a positive integer")

    client = bigquery.Client(project=bigquery_project_name)

    query = f"""
    SELECT
      COUNT(*) AS num_downloads,
      DATE_TRUNC(DATE(timestamp), MONTH) AS `month`,
      file.project AS `project`
    FROM `bigquery-public-data.pypi.file_downloads`
    WHERE
      details.ci is NULL
      AND DATE(timestamp)
        BETWEEN DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL {months_back + 1} MONTH), MONTH)
        AND LAST_DAY(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH))
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


def get_conda_pkg_download_stats(
    list_of_packages: list[str], months_back: int
) -> pd.DataFrame:
    """Get conda download stats for a list of packages.

    Args:
        list_of_packages (list[str]): List of package names to query.
        months_back (int): Number of months to generate in the past from the current date.

    Returns:
        pd.DataFrame: DataFrame containing the number of downloads for each package, grouped by month and project.
    """
    # Validate and sanitize months_back
    try:
        months_back = int(months_back)
    except (ValueError, TypeError):
        raise ValueError("months_back must be an integer")

    if months_back <= 0:
        raise ValueError("months_back must be a positive integer")

    previous_months_df = get_conda_download_trends(previous_months=months_back)
    filtered = previous_months_df[
        previous_months_df["pkg_name"]
        .str.casefold()
        .isin([pkg.casefold() for pkg in list_of_packages])
    ]
    grouped = (
        filtered.groupby(["pkg_name", "time"], observed=True)["counts"]
        .sum()
        .reset_index()
    )
    return grouped


def identify_missing_data(
    package_df: pd.DataFrame, cached_df: pd.DataFrame | None, months_back: int
) -> tuple[list[str], list[str], list[str]]:
    """Identify which tools are new and which months need to be queried.

    Args:
        package_df (pd.DataFrame): Current package information with pypi_package_name column.
        cached_df (pd.DataFrame | None): Previously cached data with package names and month columns, or None if no cache exists.
        months_back (int): Total number of months that should be present.

    Returns:
        tuple[list[str], list[str], list[str]]: A tuple containing:
            - new_tools: List of package names not in cache (need all months)
            - existing_tools: List of package names already in cache
            - missing_months: List of month columns (YYYY-MM) not in cache
    """
    current_packages = set(
        package_df["pypi_package_name"].dropna().str.casefold().unique()
    )

    # Generate expected month columns
    expected_months = set(get_expected_month_columns(months_back))

    if cached_df is None or cached_df.empty:
        return list(current_packages), [], sorted(list(expected_months), reverse=True)

    cached_packages = set(
        cached_df["pypi_package_name"].dropna().str.casefold().unique()
    )
    cached_months = set(
        col for col in cached_df.columns if col not in PACKAGE_INFO_COLUMNS
    )

    new_tools = list(current_packages - cached_packages)  # difference
    existing_tools = list(current_packages & cached_packages)  # intersection
    missing_months = sorted(list(expected_months - cached_months), reverse=True)

    return new_tools, existing_tools, missing_months


def merge_with_cached_downloads(
    new_data_df: pd.DataFrame, cached_df: pd.DataFrame | None
) -> pd.DataFrame:
    """Merge newly queried download data with cached data.

    Args:
        new_data_df (pd.DataFrame): Newly enriched data with package info and new month columns.
        cached_df (pd.DataFrame | None): Previously cached complete data, or None if no cache exists.

    Returns:
        pd.DataFrame: Combined DataFrame with all package info and all month columns.
    """
    if cached_df is None or cached_df.empty:
        return new_data_df

    # Identify month columns
    new_months = set(new_data_df.columns) - set(PACKAGE_INFO_COLUMNS)
    cached_months = set(cached_df.columns) - set(PACKAGE_INFO_COLUMNS)

    # Columns from cache that aren't in new data
    cache_only_months = cached_months - new_months

    if not cache_only_months:
        return new_data_df

    # Single merge instead of loop
    result = new_data_df.merge(
        cached_df[["id"] + list(cache_only_months)], on="id", how="left"
    )

    # Sort month columns descending
    month_cols = sorted(set(result.columns) - set(PACKAGE_INFO_COLUMNS), reverse=True)
    return result[PACKAGE_INFO_COLUMNS + month_cols]


def enrich_with_monthly_downloads(
    package_df: pd.DataFrame,
    pypi_download_stats_df: pd.DataFrame,
    conda_download_stats_df: pd.DataFrame,
) -> pd.DataFrame:
    """Add monthly download columns (wide format) to each tool row.

    Args:
        package_df (pd.DataFrame): DataFrame containing the base package information.
        pypi_download_stats_df (pd.DataFrame): DataFrame containing the monthly download statistics for pypi.
        conda_download_stats_df (pd.DataFrame): DataFrame containing the monthly download statistics for anaconda.

    Returns:
        pd.DataFrame: DataFrame containing the monthly download statistics.
    """
    base = package_df.copy()
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
@click.option(
    "--months-back",
    type=int,
    help="Number of months back to query for download trends.",
    default=24,
)
def cli(
    stats_file: Path,
    out_path: Path,
    use_bigquery: bool,
    pypi_path: Path,
    package_cache_path: Path,
    months_back: int,
) -> None:
    """CLI entry point to collect all users who interact with repositories listed in a stats file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 0 - Load cached data once if exists
    cached_df = None
    if out_path.exists():
        cached_df = pd.read_csv(out_path, index_col=False)
        LOGGER.info(f"Loaded cached data from {out_path} with {len(cached_df)} rows")

    # Step 1 - Load the statistics data from inventory/output/stats.csv
    stats_df = pd.read_csv(stats_file, usecols=["id", "html_url"])

    # Step 2 - Populate the package information columns using cached package info
    cached_package_info_df = (
        cached_df[PACKAGE_INFO_COLUMNS] if cached_df is not None else None
    )
    package_info_df = get_package_info(
        stats_df, package_cache_path, cached_package_info_df
    )

    # Step 3 - Populate the monthly downloads columns using smart caching

    # Identify what needs to be queried
    new_tools, existing_tools, missing_months = identify_missing_data(
        package_info_df, cached_df, months_back
    )

    LOGGER.info(f"New tools: {len(new_tools)}, Missing months: {len(missing_months)}")

    # Check if no new download data needs to be queried
    if len(new_tools) == 0 and len(missing_months) == 0:
        if cached_df is not None:
            # Cache exists and is up to date - merge with current package info
            LOGGER.info("No new download data needed - cache is up to date")
            final_df = merge_with_cached_downloads(package_info_df, cached_df)
            final_df.to_csv(out_path, index=False)
            LOGGER.info(f"Updated package info saved to {out_path}")
        else:
            # No cache and no PyPI packages - just write package info without download columns
            LOGGER.info("No PyPI packages found - writing package info only")
            package_info_df.to_csv(out_path, index=False)
        return

    # Initialize empty DataFrames
    pypi_download_stats_df = pd.DataFrame()
    anaconda_download_stats_df = pd.DataFrame()

    # Query all months for new tools
    if new_tools:
        LOGGER.info(f"Querying all {months_back} months for {len(new_tools)} new tools")
        if use_bigquery:
            pypi_new = query_file_downloads(new_tools, months_back=months_back)
        else:
            pypi_all = pd.read_csv(pypi_path)
            pypi_new = pypi_all[
                pypi_all["project"]
                .str.casefold()
                .isin([t.casefold() for t in new_tools])
            ]
        anaconda_new = get_conda_pkg_download_stats(new_tools, months_back=months_back)
        pypi_download_stats_df = pd.concat(
            [pypi_download_stats_df, pypi_new], ignore_index=True
        )
        anaconda_download_stats_df = pd.concat(
            [anaconda_download_stats_df, anaconda_new], ignore_index=True
        )

    # Query only missing months for existing tools
    if existing_tools and missing_months:
        LOGGER.info(
            f"Querying {len(missing_months)} new months for {len(existing_tools)} existing tools"
        )
        if use_bigquery:
            pypi_updates = query_file_downloads(
                existing_tools, months_back=len(missing_months)
            )
        else:
            pypi_all = pd.read_csv(pypi_path)
            pypi_updates = pypi_all[
                (
                    pypi_all["project"]
                    .str.casefold()
                    .isin([t.casefold() for t in existing_tools])
                )
                & (pypi_all["month"].astype(str).str[:7].isin(missing_months))
            ]
        anaconda_updates = get_conda_pkg_download_stats(
            existing_tools, months_back=len(missing_months)
        )
        pypi_download_stats_df = pd.concat(
            [pypi_download_stats_df, pypi_updates], ignore_index=True
        )
        anaconda_download_stats_df = pd.concat(
            [anaconda_download_stats_df, anaconda_updates], ignore_index=True
        )

    # Enrich with the queried data
    if not pypi_download_stats_df.empty or not anaconda_download_stats_df.empty:
        new_data_df = enrich_with_monthly_downloads(
            package_info_df, pypi_download_stats_df, anaconda_download_stats_df
        )
        # Merge with cached data
        final_df = merge_with_cached_downloads(new_data_df, cached_df)
        final_df.to_csv(out_path, index=False)
        LOGGER.info(f"Saved updated data to {out_path}")
    else:
        LOGGER.info("No new download data to add")


if __name__ == "__main__":
    cli()
