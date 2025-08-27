"""
GitHub Repository Fork Synchronization Script

This script automates synchronizing GitHub forks with their upstream
repositories using the GitHub API
"""

import argparse
import datetime
import os
import requests
import sys
import time
import yaml


def parse_arguments():
    """Parse command line arguments."""
    # Get default values from environment variables
    default_token = os.environ.get('GITHUB_TOKEN', '')
    default_org = os.environ.get('GITHUB_ORG', '')

    parser = argparse.ArgumentParser(
        description='Sync GitHub forks with their upstream repositories')
    parser.add_argument(
        '-t', '--token',
        default=default_token,
        help='GitHub Personal Access Token with repo scope '
             '(or set GITHUB_TOKEN env var)'
    )
    parser.add_argument(
        '-o', '--org',
        default=default_org,
        help='GitHub organization name that contains the forks '
             '(or set GITHUB_ORG env var)'
    )
    parser.add_argument(
        '-f', '--file',
        default='repos_to_fork.yaml',
        help='YAML file containing repositories that were forked'
    )
    parser.add_argument(
        '-l', '--log',
        default='sync_results.log',
        help='Log file path'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only check which forks need updates without actually syncing'
    )

    args = parser.parse_args()

    # Validate that token is provided either via args or env vars
    if not args.token:
        print("Error: GitHub token is required. Provide it with -t/--token "
              "or set GITHUB_TOKEN environment variable.")
        sys.exit(1)

    # Organization is required for this script
    if not args.org:
        print("Error: GitHub organization is required. Provide it with -o/--org "
              "or set GITHUB_ORG environment variable.")
        sys.exit(1)

    return args


def read_yaml_file(file_path):
    """Read repositories from the YAML file."""
    try:
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)
        return data
    except Exception as e:
        print(f"Error reading YAML file: {e}")
        sys.exit(1)


def get_fork_details(repo_name, org, token):
    """Get details about a fork, including its upstream repository."""
    url = f"https://api.github.com/repos/{org}/{repo_name}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        repo_data = response.json()

        # Check if this is actually a fork
        if not repo_data.get('fork', False):
            print(f"Repository {org}/{repo_name} is not a fork. Skipping.")
            return None

        # Get upstream information
        parent = repo_data.get('parent', {})
        if not parent:
            print(f"Cannot find parent repository information for "
                  f"{org}/{repo_name}. Skipping.")
            return None

        return {
            'name': repo_name,
            'upstream_owner': parent.get('owner', {}).get('login'),
            'upstream_name': parent.get('name'),
            'default_branch': parent.get('default_branch', 'main'),
            'fork_branch': repo_data.get('default_branch', 'main')
        }

    except requests.exceptions.HTTPError as e:
        print(f"Error getting fork details for {org}/{repo_name}: {e}")
        return None


def check_if_update_needed(fork_details, org, token):
    """Check if the fork needs to be updated by comparing commits."""
    if not fork_details:
        return False

    upstream_owner = fork_details['upstream_owner']
    upstream_name = fork_details['upstream_name']
    upstream_repo = f"{upstream_owner}/{upstream_name}"
    fork_repo = f"{org}/{fork_details['name']}"
    branch = fork_details['default_branch']

    # Get latest commit from upstream
    upstream_url = (f"https://api.github.com/repos/{upstream_repo}/"
                   f"commits/{branch}")
    # Get latest commit from fork
    fork_url = f"https://api.github.com/repos/{fork_repo}/commits/{branch}"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        # Get upstream commit
        upstream_response = requests.get(upstream_url, headers=headers)
        upstream_response.raise_for_status()
        upstream_commit = upstream_response.json().get('sha')

        # Get fork commit
        fork_response = requests.get(fork_url, headers=headers)
        fork_response.raise_for_status()
        fork_commit = fork_response.json().get('sha')

        # Compare commits
        return upstream_commit != fork_commit

    except requests.exceptions.HTTPError as e:
        print(f"Error checking for updates for {fork_repo}: {e}")
        return False


def sync_fork(fork_details, org, token, log_file):
    """Sync a fork with its upstream repository."""
    if not fork_details:
        return False

    upstream_owner = fork_details['upstream_owner']
    upstream_name = fork_details['upstream_name']
    upstream_repo = f"{upstream_owner}/{upstream_name}"
    fork_repo = f"{org}/{fork_details['name']}"
    branch = fork_details['default_branch']

    print(f"Syncing {fork_repo} with upstream {upstream_repo}...")

    # API endpoint to merge the upstream branch into the fork
    url = (f"https://api.github.com/repos/{org}/{fork_details['name']}/"
          f"merge-upstream")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    data = {
        "branch": branch
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()

        # Check if merge was successful
        if result.get('merged', False):
            print(f"Successfully synced {fork_repo} with upstream "
                 f"{upstream_repo}")
            with open(log_file, 'a') as log:
                timestamp = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                log.write(
                    f"[SUCCESS] {fork_repo} synced with {upstream_repo} "
                    f"at {timestamp}\n"
                )
                if 'base_branch' in result and 'head_branch' in result:
                    log.write(
                        f"  Merged {result['head_branch']} into "
                        f"{result['base_branch']}\n"
                    )
            return True
        else:
            print(f"Fork {fork_repo} is already up to date with "
                 f"{upstream_repo}")
            with open(log_file, 'a') as log:
                timestamp = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                log.write(
                    f"[UP-TO-DATE] {fork_repo} already in sync with "
                    f"{upstream_repo} at {timestamp}\n"
                )
            return True

    except requests.exceptions.HTTPError as e:
        print(f"Failed to sync {fork_repo}: {e}")
        try:
            error_details = e.response.json()
            print(f"Error details: {error_details}")
        except Exception:
            pass

        with open(log_file, 'a') as log:
            timestamp = datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            log.write(
                f"[FAILED] {fork_repo} sync with {upstream_repo} failed: "
                f"{e}\n"
            )
        return False

    except Exception as e:
        print(f"Unexpected error syncing {fork_repo}: {e}")
        with open(log_file, 'a') as log:
            timestamp = datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            log.write(f"[ERROR] {fork_repo} - Unexpected error: {e}\n")
        return False


def main():
    """Main function to process repositories and sync forks."""
    args = parse_arguments()

    # Check if YAML file exists
    if not os.path.isfile(args.file):
        print(f"Error: Repositories file '{args.file}' not found")
        sys.exit(1)

    # Initialize log file
    with open(args.log, 'w') as log:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"Fork synchronization started at {timestamp}\n")
        log.write(f"Organization: {args.org}\n")
        log.write(f"Dry run: {args.dry_run}\n")
        log.write("-----------------------------------\n")

    # Read repositories from YAML file
    data = read_yaml_file(args.file)

    # Check if the YAML has the expected structure
    if not data or 'repositories' not in data:
        print(
            "Error: Invalid YAML structure. The file should contain a "
            "'repositories' list."
        )
        sys.exit(1)

    # Process each repository
    print(f"Starting to check forks in {args.org} organization...")
    synced_count = 0
    up_to_date_count = 0
    failed_count = 0

    for repo in data['repositories']:
        # Check if repository has required fields
        if 'name' not in repo:
            print("Warning: Skipping repository with missing name")
            continue

        name = repo['name']

        # Get fork details
        fork_details = get_fork_details(name, args.org, args.token)
        if not fork_details:
            print(f"Skipping {args.org}/{name}: "
                  f"Not a fork or couldn't fetch details")
            continue

        # Check if update is needed
        needs_update = check_if_update_needed(
            fork_details, args.org, args.token
        )

        if needs_update:
            if args.dry_run:
                print(
                    f"{args.org}/{name} needs to be synced with upstream "
                    f"(dry run - not syncing)"
                )
                with open(args.log, 'a') as log:
                    timestamp = datetime.datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    log.write(
                        f"[DRY RUN] {args.org}/{name} needs sync at "
                        f"{timestamp}\n"
                    )
            else:
                # Sync the fork
                success = sync_fork(
                    fork_details, args.org, args.token, args.log
                )
                if success:
                    synced_count += 1
                else:
                    failed_count += 1
        else:
            print(f"{args.org}/{name} is already up to date with upstream")
            up_to_date_count += 1
            with open(args.log, 'a') as log:
                timestamp = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                log.write(
                    f"[UP-TO-DATE] {args.org}/{name} already in sync at "
                    f"{timestamp}\n"
                )

        # GitHub recommends waiting between API requests to avoid rate limiting
        time.sleep(1)

    # Write summary to log
    with open(args.log, 'a') as log:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write("\n-----------------------------------\n")
        log.write(f"Synchronization completed at {timestamp}\n")
        if args.dry_run:
            log.write("DRY RUN - No changes were made\n")
        log.write(f"Repositories processed: {len(data['repositories'])}\n")
        log.write(f"Already up to date: {up_to_date_count}\n")
        if not args.dry_run:
            log.write(f"Successfully synced: {synced_count}\n")
            log.write(f"Failed to sync: {failed_count}\n")

    # Print summary
    print("\nSynchronization process completed.")
    print(f"Repositories processed: {len(data['repositories'])}")
    print(f"Already up to date: {up_to_date_count}")
    if not args.dry_run:
        print(f"Successfully synced: {synced_count}")
        print(f"Failed to sync: {failed_count}")
    print(f"See {args.log} for details.")


if __name__ == "__main__":
    main()
