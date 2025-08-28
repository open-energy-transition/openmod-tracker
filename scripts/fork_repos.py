"""GitHub Repository Forking Script.

This script automates forking GitHub repositories using the GitHub API.
It reads repositories from the CSV file in inventory/output/stats.csv
and forks them to the organization specified in the .env file.
"""

import csv
import datetime
import os
import re
import sys
import time

from dotenv import load_dotenv

# Import helper functions
from github_api import (
    GITHUB_ORG,
    GITHUB_TOKEN,
    check_existing_fork,
    get_repository_details,
    sync_fork,
)
from github_api import fork_repository as github_fork_repository

# Load environment variables from .env file
load_dotenv()

# Configuration - set defaults and load from .env
CSV_FILE = "inventory/output/stats.csv"
LOG_FILE = "scripts/fork_results.log"


def validate_config():
    """Validate the configuration."""
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        print("Please set it in your .env file.")
        sys.exit(1)

    if not GITHUB_ORG:
        print("Error: GITHUB_ORG environment variable is not set.")
        print("Please set it in your .env file.")
        sys.exit(1)

    if not os.path.isfile(CSV_FILE):
        print(f"Error: CSV file '{CSV_FILE}' not found.")
        print("Please ensure the file exists or set CSV_FILE")
        print("in your .env file.")
        sys.exit(1)


def read_repos_from_csv():
    """Read repositories from the CSV file."""
    repos = []
    try:
        with open(CSV_FILE, encoding="utf-8") as file:
            reader = csv.DictReader(file)

            # Check if the CSV has the required column
            if "html_url" not in reader.fieldnames:
                print("Error: CSV file must contain a 'html_url' column.")
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
                            "description": row.get(
                                "description", f"Fork of {owner}/{name}"
                            ),
                        }
                    )

        return repos

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)


def process_repository(owner, repo_name, description):
    """Fork a GitHub repository using the GitHub API and sync if needed."""
    print(f"Checking if {owner}/{repo_name} is already forked...")

    # Check if already forked
    exists = check_existing_fork(owner, repo_name)

    if exists:
        fork_url = f"https://github.com/{GITHUB_ORG}/{repo_name}"
        print(f"Repository {owner}/{repo_name} is already forked to {GITHUB_ORG}")
        print(f"Fork URL: {fork_url}")

        # If fork exists, sync it
        print(f"Syncing fork with upstream {owner}/{repo_name}...")

        # Get default branch from repository
        repo_data = get_repository_details(GITHUB_ORG, repo_name)
        if repo_data:
            if hasattr(repo_data, "default_branch"):
                default_branch = repo_data.default_branch
            else:
                default_branch = "main"

            # Sync the fork
            sync_result = sync_fork(
                owner, repo_name, default_branch, org=GITHUB_ORG, log_file=LOG_FILE
            )
            sync_status = "synced" if sync_result else "sync failed"

            with open(LOG_FILE, "a") as log:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log.write(
                    f"[FORK-EXISTS] {owner}/{repo_name} - Fork exists and "
                    f"was {sync_status} at {timestamp}\n"
                )
                log.write(f"  Fork URL: {fork_url}\n")

            return True, f"{fork_url} ({sync_status})", sync_result
        else:
            print("Error getting repository details")

            with open(LOG_FILE, "a") as log:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log.write(
                    f"[SKIPPED] {owner}/{repo_name} - Already forked "
                    f"but sync failed at {timestamp}\n"
                )
                log.write(f"  Fork URL: {fork_url}\n")
                log.write("  Sync error: Could not get repository details\n")

            return True, fork_url, False

    # Fork the repository
    success, fork_url = github_fork_repository(
        owner, repo_name, org=GITHUB_ORG, description=description
    )

    if success:
        print(f"Successfully forked {owner}/{repo_name} to {GITHUB_ORG}")
        print(f"Fork URL: {fork_url}")

        with open(LOG_FILE, "a") as log:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log.write(f"[SUCCESS] {owner}/{repo_name} forked at {timestamp}\n")
            log.write(f"  Fork URL: {fork_url}\n")
            if description:
                log.write(f"  Description: {description}\n")
        return True, fork_url, False
    else:
        with open(LOG_FILE, "a") as log:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log.write(f"[FAILED] {owner}/{repo_name} - Forking failed\n")
        return False, None, False


def main():
    """Main function to process repositories and fork them."""
    # Validate configuration
    validate_config()

    # Ensure the directory for the log file exists
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    # Initialize log file
    with open(LOG_FILE, "w") as log:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"Fork operation started at {timestamp}\n")
        log.write(f"Organization: {GITHUB_ORG}\n")
        log.write(f"CSV File: {CSV_FILE}\n")
        log.write("-----------------------------------\n")

    # Read repositories from CSV file
    repos = read_repos_from_csv()

    if not repos:
        print("No repositories found in the CSV file.")
        sys.exit(1)

    print(f"Found {len(repos)} repositories to fork.")

    # Process each repository
    print("Starting to fork repositories...")
    successful_forks = 0
    skipped_forks = 0
    failed_forks = 0
    synced_forks = 0

    for repo in repos:
        owner = repo["owner"]
        name = repo["name"]
        description = repo.get("description", "")

        # Process the repository
        result, url, synced = process_repository(owner, name, description)

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

        # GitHub recommends waiting between API requests to avoid rate limiting
        time.sleep(2)

    # Write summary to log
    with open(LOG_FILE, "a") as log:
        log.write("\n-----------------------------------\n")
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"Forking process completed at {current_time}\n")
        log.write(f"Total repositories processed: {len(repos)}\n")
        log.write(f"Successfully forked: {successful_forks}\n")
        log.write(f"Already existed (skipped): {skipped_forks}\n")
        log.write(f"Successfully synced: {synced_forks}\n")
        log.write(f"Failed to fork: {failed_forks}\n")

    print("\nForking process completed.")
    print(f"Total repositories processed: {len(repos)}")
    print(f"Successfully forked: {successful_forks}")
    print(f"Already existed (skipped): {skipped_forks}")
    print(f"Successfully synced: {synced_forks}")
    print(f"Failed to fork: {failed_forks}")
    print(f"See {LOG_FILE} for details.")


if __name__ == "__main__":
    main()
