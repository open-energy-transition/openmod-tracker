# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Get OpenSSF Scorecard stats for defined projects."""

import logging
import os
import re
import subprocess
from pathlib import Path

import click
import pandas as pd
import requests
import tqdm
import yaml

path_cwd = Path().cwd()

LOGGER = logging.getLogger(__name__)
OSSF_SCORECARD_API = "https://api.securityscorecards.dev/projects/"


def get_tool_name_url(file_name: Path) -> pd.DataFrame:
    """Get the tool name and URL for the scorecard command.

    Parameters
    ------------
    file_name : Path
        The path to the CSV file containing the repository stats.

    Returns:
    --------
    pd.DataFrame
        A DataFrame containing the tool name and URL for the scorecard command.
    """
    stats_df = pd.read_csv(file_name)
    return stats_df[["id", "html_url"]]


def extract_aggregated_score(output: str) -> str | None:
    """Extract the aggregated score from scorecard output.

    Parameters
    ------------
        output: The full scorecard command output.

    Returns:
    --------
    str | None
        The aggregate score as a string, or None if not found.
    """
    match = re.search(r"Aggregate score:\s+([\d.]+)\s+/\s+10", output)
    return match.group(1) if match else None


def extract_check_scores(output: str) -> list[dict[str, str]]:
    """Extract individual check scores from scorecard output table.

    Parameters
    ------------
    output: str
        The full scorecard command output.

    Returns:
    --------
    list[dict[str, str]]
        A list of dictionaries with keys: score, name, reason, documentation url.
    """
    checks: list[dict[str, str]] = []

    # Split by "Check scores:" to isolate the table section
    if "Check scores:" not in output:
        return checks

    table_section = output.split("Check scores:")[1]

    # Match table rows with 4 columns: | SCORE | NAME | REASON | DOC_URL |
    pattern = r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"

    for match in re.finditer(pattern, table_section):
        score = match.group(1).strip()
        name = match.group(2).strip()
        reason = match.group(3).strip()
        doc_url = match.group(4).strip()

        # Skip header rows and separator lines
        if score == "SCORE" or score.startswith("-") or not score:
            continue

        # Only keep rows where score looks like a numeric score or N/A
        if not re.match(r"^[\d]+\s*/\s*10$|^N/A$|^\?$", score):
            continue

        # Extract only the numerator from scores like "10 / 10"
        numeric_match = re.match(r"^([\d]+)\s*/\s*10$", score)
        if numeric_match:
            score = numeric_match.group(1)

        checks.append(
            {"score": score, "name": name, "reason": reason, "doc_url": doc_url}
        )

    return checks


def parse_scorecard_output(output: str) -> tuple[float | None, pd.DataFrame]:
    """Parse the complete scorecard output and return structured data.

    Parameters
    ------------
    output: str
        The full scorecard command output.

    Returns:
    --------
    tuple[float | None, pd.DataFrame]
        A tuple containing the aggregate score (or None if not found) and a DataFrame of individual check scores with columns: name, score, reason, doc_url.
    """
    aggregate_score = extract_aggregated_score(output)
    checks = extract_check_scores(output)
    df = pd.DataFrame(checks)
    return aggregate_score, df


def check_auth_token(url):
    """Check if required auth token environment variable is set for the given URL.

    Parameters
    ------------
    url:  str
        The URL to check

    Returns:
    --------
        bool: True if the required auth token is set, False otherwise
    """
    url_lower = url.casefold()

    if "github" in url_lower:
        github_tokens = [
            "GITHUB_AUTH_TOKEN",
            "GITHUB_TOKEN",
            "GH_AUTH_TOKEN",
            "GH_TOKEN",
        ]
        return any(os.getenv(token) for token in github_tokens)

    elif "gitlab" in url_lower:
        return bool(os.getenv("GITLAB_AUTH_TOKEN"))

    return False


def get_scorecard_from_api(url: str) -> tuple[float | None, pd.DataFrame] | None:
    """Retrieve the scorecard for a repository from the scorecard API.

    Parameters
    ------------
    url : str
        The repository URL to retrieve the scorecard for.

    Returns:
    -------
    pandas.DataFrame| None
        A DataFrame containing the scorecard data if found, or None if not found in either source.

    """
    repo_data = None
    try:
        safe_query = url.removeprefix("https://")
        response = requests.get(OSSF_SCORECARD_API + safe_query)
        if response.ok and response.status_code != 500:
            repo_data = yaml.safe_load(response.content.decode("utf-8"))
        else:
            LOGGER.info(
                f"Static URL {url} returned {response.status_code} status code."
            )

        if repo_data:
            aggregated_score = repo_data.get("score", None)
            checks = repo_data.get("checks", [])
            rows = [
                {
                    "name": check["name"],
                    "score": check["score"],
                    "reason": check["reason"],
                }
                for check in checks
            ]
            df = pd.DataFrame(rows, columns=["name", "score", "reason"])
            return aggregated_score, df
    except Exception as e:
        LOGGER.warning(f"Error fetching ecosyste.ms repo data for {url}: {e}")
        return None


def get_scorecard_from_cli(url: str) -> str | None:
    """Run the scorecard command for a given repository URL and return the output.

    Parameters
    ------------
    url: str
        The repository URL to run scorecard on.

    Returns:
    --------
    str | None
        The full output from the scorecard command if successful, None otherwise.

    Raises:
    ------
    FileNotFoundError
        If the 'scorecard' command is not found in the system PATH.
    """
    if not check_auth_token(url):
        LOGGER.warning(f"No auth token available for {url}, skipping scorecard CLI.")
        return None

    command: list[str] = ["scorecard", f"--repo={url}"]
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        output_lines = []

        # Read stdout line by line
        for line in process.stdout:
            if "error" in line.lower():
                print(line, end="")
            output_lines.append(line)

        process.wait()

        full_output = "".join(output_lines)
        if process.returncode == 0:
            return full_output
        else:
            LOGGER.error(
                f"Error: scorecard failed with return code {process.returncode}"
            )
            LOGGER.error(f"stderr: {process.stderr}")
            return None
    except FileNotFoundError:
        LOGGER.error(
            "Error: 'scorecard' command not found. Ensure it is installed and in PATH."
        )
        return None


def get_scorecard_from_csv(csv_path: Path) -> pd.DataFrame | None:
    """Load scorecard data from CSV file.

    Parameters
    ------------
    csv_path : Path
        The path to the CSV file containing scorecard data.

    Returns:
    --------
    pd.DataFrame | None
        The scorecard DataFrame if found, None otherwise.
    """
    if csv_path.exists():
        score_card = pd.read_csv(csv_path, index_col="id")
        return score_card
    else:
        LOGGER.warning(f"CSV file not found at {csv_path}")
        return None


def process_repositories(
    stats_path: Path, scores_path: Path, reasons_path: Path, batch_size: int = 5
) -> None:
    """Read repository URLs and run scorecard on each one.

    Parameters
    ----------
    stats_path : Path
        Path to the CSV file containing repository stats with 'id' and 'html_url'
        columns.
    scores_path : Path
        Output path for the scores CSV file. Columns include 'id', 'html_url',
        'aggregated_score', and individual check scores.
    reasons_path : Path
        Output path for the reasons CSV file. Columns include 'id', 'html_url',
        and individual check reasons prefixed with 'Reason '.
    batch_size : int, optional
        Number of repositories to process before writing a batch to CSV. Default is 5.

    Raises:
    ------
    ValueError
        If no scorecard results were collected after processing all repositories
        or if a repository fails all fallback methods (API → CLI → CSV).
    """
    stats_df = get_tool_name_url(stats_path)
    existing_scores_df = get_scorecard_from_csv(scores_path)
    existing_reasons_df = get_scorecard_from_csv(reasons_path)

    score_rows: list[dict] = []
    reason_rows: list[dict] = []

    rows = list(stats_df.iterrows())
    pbar = tqdm.tqdm(rows, total=len(rows), desc="Processing repositories")
    for _, row in rows:
        pbar.update(1)
        url = row["html_url"]
        tool_name = row["id"]
        LOGGER.info(f"Processing repository: {tool_name} ({url})")

        scorecard_data = _get_scorecard_data(
            url, tool_name, existing_scores_df, existing_reasons_df
        )

        if scorecard_data is None:
            LOGGER.warning(f"Failed to get scorecard results for {tool_name}")
            continue

        aggregate_score, checks_df = scorecard_data
        score_row, reason_row = _append_scorecard_rows(
            tool_name, url, aggregate_score, checks_df
        )
        score_rows.append(score_row)
        reason_rows.append(reason_row)

        # Write batch every N rows
        if len(score_rows) >= batch_size:
            _write_batch_to_csv(score_rows, scores_path, "scores")
            _write_batch_to_csv(reason_rows, reasons_path, "reasons")
            score_rows.clear()
            reason_rows.clear()

    # Write remaining rows
    if score_rows or reason_rows:
        _write_batch_to_csv(score_rows, scores_path, "scores")
        _write_batch_to_csv(reason_rows, reasons_path, "reasons")

    if not score_rows or not reason_rows:
        raise ValueError("No scorecard results were collected.")
    pbar.close()


def _get_scorecard_data(
    url: str,
    tool_name: str,
    cache_scores_df: pd.DataFrame,
    cache_reasons_df: pd.DataFrame,
) -> tuple[float, pd.DataFrame] | None:
    """Retrieve scorecard data using fallback strategy (API → CLI → CSV).

    Parameters
    ----------
    url : str
        Repository URL to fetch scorecard data for.
    tool_name : str
        Identifier of the tool/repository (used for CSV lookup).
    cache_scores_df : pd.DataFrame
        DataFrame with existing scores, indexed by tool name. Used as fallback.
    cache_reasons_df : pd.DataFrame
        DataFrame with existing reasons, indexed by tool name. Used as fallback.

    Returns:
    -------
    tuple[float, pd.DataFrame] or None
        A tuple of (aggregated_score, checks_df) where aggregated_score is a
        float and checks_df is a DataFrame with 'name', 'score', and 'reason'
        columns. Returns None if all fallback methods fail.
    """
    # Try API
    api_result = get_scorecard_from_api(url)
    if api_result is not None:
        LOGGER.info(f"Got scorecard from API for: {url}")
        return api_result

    # Try CLI
    LOGGER.info(f"API failed, running scorecard command for: {url}")
    result = get_scorecard_from_cli(url)
    if result:
        aggregate_score, checks_df = parse_scorecard_output(result)
        return aggregate_score, checks_df

    # Try CSV fallback
    LOGGER.warning(f"CLI failed, falling back to CSV for: {url}")
    if tool_name in cache_scores_df.index and tool_name in cache_reasons_df.index:
        LOGGER.info(f"Loaded scorecard from CSV for: {url}")
        return None

    LOGGER.error(f"No CSV fallback available for: {url}")
    return None


def _append_scorecard_rows(
    tool_name: str, url: str, aggregate_score: float, checks_df: pd.DataFrame
) -> tuple[dict, dict]:
    """Extract scorecard data and return score and reason rows.

    Processes a single repository's scorecard results and returns formatted
    dictionaries ready to be appended to result lists.

    Parameters
    ----------
    tool_name : str
        Identifier of the tool/repository.
    url : str
        Repository URL.
    aggregate_score : float
        The aggregated scorecard score (typically 0-10).
    checks_df : pd.DataFrame
        DataFrame with columns: 'name' (check name), 'score' (numeric score),
        'reason' (explanation string). Rows are sorted alphabetically before
        processing.

    Returns:
    -------
    tuple[dict, dict]
        A tuple of (score_row, reason_row) where:
        - score_row contains 'id', 'html_url', 'aggregated_score', and
          individual check scores.
        - reason_row contains 'id', 'html_url', and individual check reasons
          prefixed with 'Reason '.

    Notes:
    -----
    Check reasons are capitalized. Missing values are filled with 'N/A'
    during CSV export by the caller.
    """
    checks_df = checks_df.sort_values("name").reset_index(drop=True)

    check_scores = {check["name"]: check["score"] for _, check in checks_df.iterrows()}
    check_reasons = {
        f"Reason {check['name']}": check["reason"].capitalize()
        for _, check in checks_df.iterrows()
    }

    score_row = {
        "id": tool_name,
        "html_url": url,
        "aggregated_score": aggregate_score,
        **check_scores,
    }

    reason_row = {"id": tool_name, "html_url": url, **check_reasons}

    return score_row, reason_row


def _write_batch_to_csv(rows: list[dict], path: Path, file_type: str) -> None:
    """Write a batch of rows to CSV, appending if file exists.

    Parameters
    ------------
    rows : list[dict]
        List of dictionaries representing rows to write to CSV.
    path : Path
        The path to the CSV file to write to.
    file_type : str
        A string indicating the type of file being written (e.g., "scores" or "reasons") for logging purposes.
    """
    if not rows:
        return

    # It can happen that the API response and the CLI response return different sets of checks.
    # For example tool A (API) might have checks X, Y, Z while tool B (CLI) might have checks X, Y, W.
    # When we convert these to DataFrames and save to CSV, the missing check W for tool A will be
    # NaN in the scores and reasons DataFrames. Similarly, for the missing check Z for tool B.
    # Hence, we fill missing values with "N/A" and convert
    # all to string before saving to CSV to ensure consistent formatting.
    df = pd.DataFrame(rows).fillna("N/A").astype(str)

    df.to_csv(
        path,
        mode="a",
        header=not path.exists(),  # Write header only if file doesn't exist
        index=False,
    )
    LOGGER.info(f" ---> Written {len(rows)} rows to {file_type} CSV")


@click.command()
@click.option(
    "--stats-file",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
    help="Path to the stats.csv file.",
    default="inventory/output/stats.csv",
)
@click.option(
    "--scores-file",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
    help="Output path for the scores file.",
    default="inventory/output/scores.csv",
)
@click.option(
    "--reasons-file",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
    help="Output path for the reasons of the scores file.",
    default="inventory/output/reasons.csv",
)
def cli(stats_file: Path, scores_file: Path, reasons_file: Path):
    """CLI entry point to get OpenSSF Scorecard stats for defined projects."""
    logging.basicConfig(level=logging.INFO)
    stats_path = path_cwd / stats_file
    scores_path = path_cwd / scores_file
    reasons_path = path_cwd / reasons_file
    process_repositories(stats_path, scores_path, reasons_path)


if __name__ == "__main__":
    cli()
