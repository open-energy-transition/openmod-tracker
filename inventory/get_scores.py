# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Get OpenSSF Scorecard stats for defined projects."""

import subprocess
import pathlib
import pandas as pd
import re
import logging
import argparse

path_cwd = pathlib.Path().cwd()

LOGGER = logging.getLogger(__name__)

def get_tool_name_url(file_name: str) -> pd.DataFrame:
    """
    Get the tool name and URL for the scorecard command.

    Returns:
        A DataFrame containing the tool name and URL for the scorecard command.
    """
    stats_file = pathlib.Path(path_cwd, "inventory", "output", file_name)
    stats_df = pd.read_csv(stats_file)
    return stats_df[["id", "html_url"]]


def extract_aggregate_score(output: str) -> float | None:
    """
    Extract the aggregate score from scorecard output.

    Args:
        output: The full scorecard command output.

    Returns:
        The aggregate score as a float, or None if not found.
    """
    match = re.search(r'Aggregate score:\s+([\d.]+)\s+/\s+10', output)
    return float(match.group(1)) if match else None


def extract_check_scores(output: str) -> list[dict[str, str]]:
    """
    Extract individual check scores from scorecard output table.

    Args:
        output: The full scorecard command output.

    Returns:
        A list of dictionaries with keys: score, name, reason.
    """
    checks: list[dict[str, str]] = []

    # Split by "Check scores:" to isolate the table section
    if "Check scores:" not in output:
        return checks

    table_section = output.split("Check scores:")[1]

    # Match table rows with 4 columns: | SCORE | NAME | REASON | DOC_URL |
    pattern = r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|'

    for match in re.finditer(pattern, table_section):
        score = match.group(1).strip()
        name = match.group(2).strip()
        reason = match.group(3).strip()
        doc_url = match.group(4).strip()

        # Skip header rows and separator lines
        if score == "SCORE" or score.startswith("-") or not score:
            continue

        # Only keep rows where score looks like a numeric score or N/A
        if not re.match(r'^[\d]+\s*/\s*10$|^N/A$|^\?$', score):
            continue

        checks.append({
            'score': score,
            'name': name,
            'reason': reason,
            'doc_url': doc_url
        })

    return checks


def parse_scorecard_output(output: str) -> tuple[float | None, pd.DataFrame]:
    """
    Parse the complete scorecard output and return structured data.

    Args:
        output: The full scorecard command output.

    Returns:
        A tuple containing (aggregate_score, DataFrame with check results).
        The DataFrame has columns: score, name, reason.
    """
    aggregate_score = extract_aggregate_score(output)
    checks = extract_check_scores(output)
    df = pd.DataFrame(checks)
    return aggregate_score, df


def run_scorecard(url: str) -> str | None:
    """
    Run the scorecard command for a given repository URL and return the output.

    Args:
        url: The repository URL to pass to scorecard.

    Returns:
        The stdout output from the scorecard command, or None if the command failed.

    Raises:
        FileNotFoundError: If the scorecard command is not found in PATH.
    """
    command: list[str] = ['scorecard', f'--repo={url}']
    print(f"Running command: {' '.join(command)}")
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        output_lines = []

        # Read stdout line by line
        for line in process.stdout:
            print(line, end=' ')  # Print to console
            output_lines.append(line)

        process.wait()

        full_output = ''.join(output_lines)
        if process.returncode == 0:
            return full_output
        else:
            LOGGER.error(f"Error: scorecard failed with return code {process.returncode}")
            LOGGER.error(f"stderr: {process.stderr}")
            return None
    except FileNotFoundError:
        LOGGER.error(f"Error: 'scorecard' command not found. Ensure it is installed and in PATH.")
        return None


def process_repositories(file_name: str) -> None:
    """
    Read repository URLs from the stats.csv file and run scorecard on each one.

    Args:
        file_name: The name of the CSV file containing repository URLs (default: "stats.csv").
    """
    try:
        stats_df = get_tool_name_url(file_name)
        tool_names = list(stats_df['id'].dropna().unique())
        urls = list(stats_df['html_url'].dropna().unique())
        for url in urls:
            LOGGER.info(f"Running scorecard for: {url}")
            result = run_scorecard(url)
            if result:
                aggregate_score, checks_df = parse_scorecard_output(result)
                print(f"Aggregate score for {url}: {aggregate_score}")
                print(f"Check scores for {url}:\n{checks_df}")
            else:
                LOGGER.error(f"Failed to get  scorecard results for {url}")
    except Exception as e:
        LOGGER.error(f"An error occurred while processing repositories: {e}")


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the benchmark generation script.

    Returns
    -------
    argparse.Namespace
        An object containing the parsed command-line arguments as attributes.
        The attributes include `benchmark_name`, `file_extension`, `output_dir`,
        `dry_run`, `clusters`, and `time_resolutions`.
    """
    p = argparse.ArgumentParser()
    p.add_argument(
        "--file_name", default="stats.csv"
    )
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    process_repositories(args.file_name)
