"""GitHub Repository Forking Script.

This script automates forking GitHub repositories using the GitHub API.
It reads repositories from the CSV file in inventory/output/stats.csv
and forks them to the specified organization.
"""

import csv
import logging
import os
import re
import sys
import time
import click
from pathlib import Path
from github_api import GitHubAPI
from util import log_to_file

# Set up logging
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

# Set up console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
LOGGER.addHandler(console_handler)

# Set up default file handler
log_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log_dir = Path("log")
log_dir.mkdir(exist_ok=True)
default_log_file = log_dir / "fork_repos.log"
file_handler = logging.FileHandler(default_log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_formatter)
LOGGER.addHandler(file_handler)


def validate_config(csv_file, github_org, token=None):
    """Validate the configuration."""

    if not token:
        LOGGER.error("GitHub token is not provided.")
        LOGGER.error("Please provide it with --token option.")
        sys.exit(1)

    if not github_org:
        LOGGER.error("GitHub organization name is not provided.")
        sys.exit(1)

    if not os.path.isfile(csv_file):
        LOGGER.error(f"CSV file '{csv_file}' not found.")
        LOGGER.error(
            "Please ensure the file exists or specify with --csv option."
        )
        sys.exit(1)


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
                    repos.append(
                        {
                            "owner": owner,
                            "name": name,
                        }
                    )

        return repos

    except Exception as e:
        LOGGER.error(f"Error reading CSV file: {e}")
        sys.exit(1)


def process_repository(
    owner, repo_name, destination_org, token=None, log_file=None
):
    """Fork a GitHub repository using the GitHub API and sync if needed."""
    LOGGER.info(f"Checking if {owner}/{repo_name} is already forked...")

    # Create a GitHubAPI instance with the provided token
    github_api = GitHubAPI(token, destination_org)

    # Check if already forked
    exists = github_api.check_existing_fork(
        owner,
        repo_name,
    )

    if exists:
        fork_url = f"https://github.com/{destination_org}/{repo_name}"
        LOGGER.info(
            f"Repository {owner}/{repo_name} is already forked "
            f"to {destination_org}"
        )
        LOGGER.info(f"Fork URL: {fork_url}")

        # If fork exists, sync it
        LOGGER.info(f"Syncing fork with upstream {owner}/{repo_name}...")

        # Get default branch from repository
        repo_data = github_api.get_repository_details(
            destination_org,
            repo_name
        )
        if repo_data:
            if hasattr(repo_data, "default_branch"):
                default_branch = repo_data.default_branch
            else:
                default_branch = "main"

            # Sync the fork
            sync_result = github_api.sync_fork(
                owner,
                repo_name,
                default_branch,
                org=destination_org
            )
            sync_status = "synced" if sync_result else "sync failed"

            LOGGER.info(
                f"[FORK-EXISTS] {owner}/{repo_name} - Fork exists and "
                f"was {sync_status}"
            )
            LOGGER.info(f"  Fork URL: {fork_url}")

            if hasattr(github_api, 'log_file') and github_api.log_file:
                log_to_file(
                    github_api.log_file,
                    "FORK-EXISTS",
                    f"{owner}/{repo_name} - Fork exists and was {sync_status}"
                )

            return True, f"{fork_url} ({sync_status})", sync_result
        else:
            LOGGER.error("Error getting repository details")

            LOGGER.warning(
                f"[SKIPPED] {owner}/{repo_name} - Already forked "
                f"but sync failed"
            )
            LOGGER.warning(f"  Fork URL: {fork_url}")
            LOGGER.warning("  Sync error: Could not get repository details")

            return True, fork_url, False

    # Fork the repository
    success, fork_url = github_api.fork_repository(
        owner, repo_name, destination_org=destination_org
    )

    if success:
        LOGGER.info(
            f"Successfully forked {owner}/{repo_name} to {destination_org}"
        )
        LOGGER.info(f"Fork URL: {fork_url}")

        LOGGER.info(f"[SUCCESS] {owner}/{repo_name} forked")
        LOGGER.info(f"  Fork URL: {fork_url}")

        log_to_file(
            log_file,
            "SUCCESS",
            f"{owner}/{repo_name} forked to {destination_org}"
        )

        return True, fork_url, False
    else:
        LOGGER.error(f"[FAILED] {owner}/{repo_name} - Forking failed")

        log_to_file(
            log_file,
            "FAILED",
            f"{owner}/{repo_name} - Forking to {destination_org} failed"
        )

        return False, None, False


@click.command()
@click.option(
    "--csv",
    "-c",
    "csv_file",
    default="inventory/output/stats.csv",
    help="Path to the CSV file containing repository information.",
    type=click.Path(
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True
    ),
)
@click.option(
    "--org",
    "-o",
    "github_org",
    help="GitHub organization name where repositories will be forked.",
)
@click.option(
    "--log",
    "-l",
    "log_file",
    default=str(default_log_file),
    help="Path to the log file.",
    type=click.Path(
        file_okay=True,
        dir_okay=False,
        writable=True
    ),
)
@click.option(
    "--token",
    "-t",
    "github_token",
    help="GitHub token with 'repo' scope for API access.",
    required=True,
)
def main(csv_file, github_org, log_file, github_token):
    """Fork GitHub repositories from a CSV file to a specified organization.

    This command reads repository information from a CSV file and forks
    each repository to the specified GitHub organization.
    """
    # Use custom log file if provided and different from default
    if log_file != str(default_log_file):
        # Remove default file handler
        LOGGER.removeHandler(file_handler)

        # Add custom file handler
        custom_file_handler = logging.FileHandler(log_file)
        custom_file_handler.setLevel(logging.DEBUG)
        custom_file_handler.setFormatter(log_formatter)
        LOGGER.addHandler(custom_file_handler)

        # Ensure the directory for the log file exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Validate configuration
    validate_config(csv_file, github_org, github_token)

    # Log operation start
    LOGGER.info("Fork operation started")
    LOGGER.info(f"Organization: {github_org}")
    LOGGER.info(f"CSV File: {csv_file}")
    LOGGER.info("-----------------------------------")

    # Read repositories from CSV file
    repos = read_repos_from_csv(csv_file)

    if not repos:
        LOGGER.error("No repositories found in the CSV file.")
        sys.exit(1)

    LOGGER.info(f"Found {len(repos)} repositories to fork.")

    # Process each repository
    LOGGER.info("Starting to fork repositories...")
    successful_forks = 0
    skipped_forks = 0
    failed_forks = 0
    synced_forks = 0

    for repo in repos:
        owner = repo["owner"]
        name = repo["name"]

        # Process the repository
        result, url, synced = process_repository(
            owner, name, github_org, github_token, log_file
        )

        if result:
            has_fork_text = (
                "already forked" in str(url).lower()
                or "fork exists" in str(url).lower()
            )
            if has_fork_text:
                skipped_forks += 1
                if synced:
                    synced_forks += 1
            else:
                successful_forks += 1
        else:
            failed_forks += 1

        # Avoid rate limiting
        time.sleep(2)

    # Write summary to log
    LOGGER.info("\n-----------------------------------")
    LOGGER.info("Forking process completed")
    LOGGER.info(f"Total repositories processed: {len(repos)}")
    LOGGER.info(f"Successfully forked: {successful_forks}")
    LOGGER.info(f"Already existed (skipped): {skipped_forks}")
    LOGGER.info(f"Successfully synced: {synced_forks}")
    LOGGER.info(f"Failed to fork: {failed_forks}")
    LOGGER.info(f"See {log_file} for details.")


if __name__ == "__main__":
    main()
