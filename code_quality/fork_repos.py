# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""GitHub Repository Forking Script.

This script automates forking GitHub repositories using the GitHub API.
It reads repositories from the CSV file in inventory/output/stats.csv
and forks them to the specified organization.
"""

import csv
import logging
import re
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import click
import pandas as pd
from git_api import GitAPI
from tqdm import tqdm
from util import set_logging_handlers

# Set up logging
LOGGER = logging.getLogger(__name__)


def read_repos_from_csv(csv_file):
    """Read repositories from the CSV file."""
    repos = []
    try:
        with open(csv_file, encoding="utf-8") as file:
            reader = csv.DictReader(file)

            # Check if the CSV has the required column
            if "html_url" not in reader.fieldnames:
                LOGGER.error("CSV file must contain a 'html_url' column.")
                sys.exit(1)

            for row in reader:
                url = row.get("html_url", "")
                if not url or not url.startswith("https://github.com/"):
                    continue

                # Extract owner and repo name from GitHub URL
                match = re.match(r"https://github.com/([^/]+)/([^/]+)", url)
                if match:
                    owner, name = match.groups()
                    repos.append({"owner": owner, "name": name})

        return repos

    except Exception as e:
        LOGGER.error(f"Error reading CSV file: {e}")
        sys.exit(1)


def process_non_github_repository(
    url: str, repo_name: str, destination_org: str
) -> Literal["forked", "synced", "sync failed", "fork failed"]:
    """Process a non-GitHub repository.

    Returns:
        Literal["forked", "synced", "sync failed", "fork failed"]: The result of the operation.
    """
    # Create a GitAPI instance with the provided token
    github_api = GitAPI(destination_org)
    result = github_api.process_non_github_url(url, destination_org, repo_name)
    return result


def process_github_repository(
    upstream_owner: str, repo_name: str, destination_org: str
) -> Literal["forked", "synced", "sync failed", "fork failed"]:
    """Fork a GitHub repository using the GitHub API and sync if needed.

    Args:
        upstream_owner (str): Owner of the original repository.
        repo_name (str): Name of the repository.
        destination_org (str): GitHub organization to fork the repository to.

    Returns:
        str: Result of the operation: "forked", "synced", "sync failed", or "fork failed".
    """
    # Create a GitAPI instance with the provided token
    github_api = GitAPI(destination_org)

    # Check if already forked
    exists = github_api.check_existing_fork(upstream_owner, repo_name)
    result: Literal["forked", "synced", "sync failed", "fork failed"]

    if exists:
        fork_url = f"https://github.com/{destination_org}/{repo_name}"
        LOGGER.info(
            f"Repository {upstream_owner}/{repo_name} is already forked to {destination_org}. "
            f"Fork URL: {fork_url}. Checking if sync is needed..."
        )

        # Get default branch from repository
        repo_data = github_api.get_repository_details(repo_name)
        if repo_data:
            if hasattr(repo_data, "default_branch"):
                default_branch = repo_data.default_branch
            else:
                default_branch = "main"

            # Sync the fork
            sync_result = github_api.sync_fork(
                upstream_owner, repo_name, default_branch
            )
            sync_status = "synced" if sync_result else "sync failed"

            LOGGER.info(
                f"[FORK-EXISTS] {upstream_owner}/{repo_name} - Fork exists and was {sync_status}. Fork URL: {fork_url}"
            )

            if hasattr(github_api, "log_file") and github_api.log_file:
                LOGGER.info(
                    f"{upstream_owner}/{repo_name} - Fork exists and was {sync_status}"
                )

            result = sync_status
        else:
            LOGGER.error("Error getting repository details")
            LOGGER.warning(
                f"[SKIPPED] {upstream_owner}/{repo_name} - Already forked but sync failed. Fork URL: {fork_url}"
            )

            result = "sync failed"
    else:
        # Fork the repository
        success, fork_url = github_api.fork_repository(upstream_owner, repo_name)

        if success:
            LOGGER.info(
                f"Successfully forked {upstream_owner}/{repo_name} to {destination_org}"
                f"Fork URL: {fork_url}"
            )

            result = "forked"
        else:
            LOGGER.error(
                f"[FAILED] {upstream_owner}/{repo_name} - Forking to {destination_org} failed"
            )

            result = "fork failed"
    return result


@click.command()
@click.argument(
    "repo_urls_csv",
    default="inventory/output/stats.csv",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, readable=True, path_type=Path
    ),
)
@click.argument("github_org", default="openmod-tracker", type=str)
@click.option(
    "--log",
    "-l",
    "log_file",
    default="logs/fork_repos.log",
    help="Path to the log file.",
    type=click.Path(file_okay=True, dir_okay=False, writable=True, path_type=Path),
)
def cli(repo_urls_csv: Path, github_org, log_file):
    """Fork GitHub repositories from a CSV file to a specified organization.

    REPO_URLS_CSV: Path to the CSV file containing repository information.
    GITHUB_ORG: GitHub organization name where repositories will be forked.
    """
    # Use custom log file if provided and different from default
    set_logging_handlers(LOGGER, log_file)

    # Log operation start
    LOGGER.info("Fork operation started")
    LOGGER.info(f"Organization: {github_org}")
    LOGGER.info(f"CSV File: {repo_urls_csv}")
    LOGGER.info("-----------------------------------")

    successful_forks = 0
    failed_syncs = 0
    failed_forks = 0
    synced_forks = 0

    repos_df = pd.read_csv(repo_urls_csv, index_col="html_url")
    for repo_url in tqdm(repos_df.index, desc="Creating/syncing forks"):
        url_parts = urlparse(repo_url)
        LOGGER.info(f"Processing {repo_url}")
        orig_org, repo = url_parts.path.strip("/").rsplit("/", 1)
        if url_parts.netloc.endswith("github.com"):
            result = process_github_repository(orig_org, repo, github_org)
        else:
            result = process_non_github_repository(repo_url, repo, github_org)

        if result == "forked":
            successful_forks += 1
        elif result == "synced":
            synced_forks += 1
        elif result == "sync failed":
            failed_syncs += 1
        elif result == "fork failed":
            failed_forks += 1

    # Write summary to log
    LOGGER.info(
        f"""-----------------------------------
        Forking process completed.

        Total repositories processed: {len(repos_df)}
        Successfully forked: {successful_forks}
        Successfully synced existing fork: {synced_forks}
        Failed to fork: {failed_forks}
        Failed to sync existing fork: {failed_syncs}
        See {log_file} for details."""
    )


if __name__ == "__main__":
    cli()
