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
import util

path_cwd = Path().cwd()

LOGGER = logging.getLogger(__name__)
OSSF_SCORECARD_API = "https://api.securityscorecards.dev/projects/"


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
    try:
        safe_query = url.removeprefix("https://")
        repo_data = util.get_ecosystems_data(OSSF_SCORECARD_API + safe_query)
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
        try:
            score_card = pd.read_csv(csv_path, index_col="id")
            return score_card
        except Exception as e:
            LOGGER.error(f"Error reading CSV file {csv_path}: {e}")
            return None
    else:
        LOGGER.debug(f"CSV file not found at {csv_path}")
        return None


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
            print(line, end=" ")
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


def process_repositories(
    stats_path: Path, scores_path: Path, reasons_path: Path
) -> None:
    """Read repository URLs and run scorecard on each one.

    Parameters
    ------------
    stats_path: Path
        The path to the CSV file containing repository stats with 'id' and 'html_url'
    scores_path: Path
        The output path for the scores CSV file.
    reasons_path: Path
        The output path for the reasons CSV file.

    Raises:
    ------
    ValueError
        If no scorecard results were collected or processing fails.
    """
    stats_df = get_tool_name_url(stats_path)
    score_rows: list[dict] = []
    reason_rows: list[dict] = []

    for _, row in stats_df.iterrows():
        url = row["html_url"]
        tool_name = row["id"]

        if "pypsa" not in url.casefold() and "ego" not in url.casefold():
            continue

        LOGGER.info(f"Trying scorecard API for: {url}")
        api_result = get_scorecard_from_api(url)

        if api_result is not None:
            aggregate_score, checks_df = api_result
            print(f"Got scorecard from API for: {url}")
        else:
            LOGGER.info(f"API failed, running scorecard command for: {url}")
            result = get_scorecard_from_cli(url)
            if not result:
                raise ValueError(f"Failed to get scorecard results for {url}")
            aggregate_score, checks_df = parse_scorecard_output(result)

        checks_df = checks_df.sort_values("name").reset_index(drop=True)

        score_rows.append(
            {
                "id": tool_name,
                "html_url": url,
                "aggregated_score": aggregate_score,
                **{check["name"]: check["score"] for _, check in checks_df.iterrows()},
            }
        )
        reason_rows.append(
            {
                "id": tool_name,
                "html_url": url,
                **{
                    f"Reason {check['name']}": check["reason"].capitalize()
                    for _, check in checks_df.iterrows()
                },
            }
        )

    if not score_rows or not reason_rows:
        raise ValueError("No scorecard results were collected.")

    # It can happen that the API response and the CLI response return different sets of checks.
    # For example tool A (API) might have checks X, Y, Z while tool B (CLI) might have checks X, Y, W.
    # When we convert these to DataFrames and save to CSV, the missing check W for tool A will be
    # NaN in the scores and reasons DataFrames. Similarly, for the missing check Z for tool B.
    # Hence, we fill missing values with "N/A" and convert
    # all to string before saving to CSV to ensure consistent formatting.
    pd.DataFrame(score_rows).fillna("N/A").astype(str).to_csv(scores_path, index=False)
    pd.DataFrame(reason_rows).fillna("N/A").astype(str).to_csv(
        reasons_path, index=False
    )


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
    stats_path = path_cwd / stats_file
    scores_path = path_cwd / scores_file
    reasons_path = path_cwd / reasons_file
    process_repositories(stats_path, scores_path, reasons_path)


if __name__ == "__main__":
    cli()
