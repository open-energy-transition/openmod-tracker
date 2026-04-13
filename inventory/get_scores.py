# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Get OpenSSF Scorecard stats for defined projects."""

import logging
import re
import subprocess
from pathlib import Path

import click
import pandas as pd

path_cwd = Path().cwd()

LOGGER = logging.getLogger(__name__)


# def get_score_card(existing_data: pd.DataFrame) -> pd.DataFrame | None:
#     """Retrieve the scorecard for a repository from the ecosyste.ms API with CSV fallback.
#
#     Parameters
#     ----------
#     existing_data : pd.DataFrame
#         Existing scorecard data to use as a fallback if API retrieval fails.
#
#     Returns
#     -------
#     pandas.DataFrame| None
#         The scorecard DataFrame containing `id`, `data`, `last_synced_at`,
#         `repository_id`, `created_at`, and `updated_at` fields.
#         Returns None if the scorecard cannot be retrieved from API or CSV.
#
#     Notes
#     -----
#     Retrieval strategy:
#     1. First attempts to fetch from ecosyste.ms API
#     2. Falls back to CSV file if API data is unavailable
#     3. Returns None if scorecard not found in either source
#     """
#     #Try API first --> This part needs to be finalized once the API is stable. Make it such that it returns a pandas DataFrame,
#     try:
#        repo_data = util.get_ecosystems_repo_data(url)
#        if repo_data and (score_card := repo_data.get("scorecard")):
#            return score_card
#     except Exception as e:
#        LOGGER.warning(f"Error fetching ecosyste.ms repo data for {url}: {e}")
#
#     # Fallback to CSV
#     score_card = _load_scorecard_from_csv(inventory_output_path / "scores.csv")
#     if not score_card:
#         LOGGER.warning(f"No scorecard found for {url} in API or CSV")
#
#     return score_card


def _load_scorecard_from_csv(csv_path: Path) -> pd.DataFrame | None:
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


def run_scorecard(url: str) -> str | None:
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
    """Read repository URLs from the stats.csv file and run scorecard on each one.

    Parameters
    ----------
    stats_path : Path
        The path to the stats.csv file containing repository URLs.
    scores_path : Path
        The path to save the scores.csv output file.
    reasons_path : Path
        The path to save the reasons.csv output file.
    """
    try:
        stats_df = get_tool_name_url(stats_path)
        score_rows: list[dict] = []
        reason_rows: list[dict] = []

        for _, row in stats_df.iterrows():
            url = row["html_url"]
            tool_name = row["id"]

            if "pypsa" not in url.casefold():
                continue

            LOGGER.info(f"Running scorecard for: {url}")
            result = run_scorecard(url)

            if result:
                aggregate_score, checks_df = parse_scorecard_output(result)
                score_record: dict = {
                    "id": tool_name,
                    "html_url": url,
                    "aggregated_score": aggregate_score,
                }
                reason_record: dict = {"id": tool_name, "html_url": url}

                for _, check in checks_df.iterrows():
                    name = check["name"]
                    score_record[name] = check["score"]
                    reason_record[f"Reason {name}"] = check["reason"].capitalize()

                score_rows.append(score_record)
                reason_rows.append(reason_record)
            else:
                LOGGER.error(f"Failed to get scorecard results for {url}")

        if score_rows and reason_rows:
            scores_df = pd.DataFrame(score_rows)
            reasons_df = pd.DataFrame(reason_rows)
            scores_df.astype(str).to_csv(scores_path, index=False)
            reasons_df.astype(str).to_csv(reasons_path, index=False)
        else:
            LOGGER.warning("No scorecard results were collected.")

    except Exception as e:
        LOGGER.error(f"An error occurred while processing repositories: {e}")


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
