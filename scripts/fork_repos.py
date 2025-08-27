"""
GitHub Repository Forking Script
This script automates forking GitHub repositories using the GitHub API
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
        description='Fork GitHub repositories automatically')
    parser.add_argument('-t', '--token', default=default_token,
                        help='GitHub Personal Access Token with repo scope (or set GITHUB_TOKEN env var)')
    parser.add_argument('-o', '--org', default=default_org,
                        help='Target GitHub organization name (or set GITHUB_ORG env var)')
    parser.add_argument('-f', '--file', default='repos_to_fork.yaml',
                        help='YAML file containing repositories to fork')
    parser.add_argument('-l', '--log', default='fork_results.log',
                        help='Log file path')

    args = parser.parse_args()

    # Validate that token is provided either via args or env vars
    if not args.token:
        print("Error: GitHub token is required. Provide it with -t/--token or set GITHUB_TOKEN environment variable.")
        sys.exit(1)

    # Organization is required
    if not args.org:
        print("Error: GitHub organization is required. Provide it with -o/--org or set GITHUB_ORG environment variable.")
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


def check_existing_fork(owner, repo_name, org, token):
    """Check if the repository is already forked by the organization."""
    url = f"https://api.github.com/repos/{org}/{repo_name}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            repo_data = response.json()
            source_repo = f"{owner}/{repo_name}"
            if (repo_data.get('fork', False) and
                    repo_data.get('source', {}).get('full_name') == source_repo):
                return True
        return False
    except Exception as e:
        print(f"Error checking existing fork: {e}")
        return False


def fork_repository(owner, repo_name, description, token, org, log_file):
    """Fork a GitHub repository using the GitHub API."""
    print(f"Checking if {owner}/{repo_name} is already forked...")

    # Check if already forked
    if check_existing_fork(owner, repo_name, org, token):
        fork_url = f"https://github.com/{org}/{repo_name}"
        print(f"Repository {owner}/{repo_name} is already forked to {org}")
        print(f"Fork URL: {fork_url}")
        with open(log_file, 'a') as log:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log.write(
                f"[SKIPPED] {owner}/{repo_name} - Already forked at {timestamp}\n")
            log.write(f"  Fork URL: {fork_url}\n")
        return True, fork_url

    print(f"Attempting to fork {owner}/{repo_name}...")

    url = f"https://api.github.com/repos/{owner}/{repo_name}/forks"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    # Add organization parameter
    data = {"organization": org}
    print(f"Target organization: {org}")

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        # Extract fork information from response
        fork_data = response.json()
        fork_url = fork_data.get('html_url')

        print(f"Successfully forked {owner}/{repo_name} to {org}")
        print(f"Fork URL: {fork_url}")

        with open(log_file, 'a') as log:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log.write(f"[SUCCESS] {owner}/{repo_name} forked at {timestamp}\n")
            log.write(f"  Fork URL: {fork_url}\n")
            if description:
                log.write(f"  Description: {description}\n")
        return True, fork_url

    except requests.exceptions.HTTPError as e:
        print(f"Failed to fork {owner}/{repo_name}: {e}")

        try:
            error_details = e.response.json()
            print(f"Error details: {error_details}")

            # Special handling for token permission errors
            if error_details.get('message') == 'Resource not accessible by personal access token':
                print(
                    "\nERROR: Your GitHub token doesn't have the necessary permissions.")
                print("You need to create a new token with the 'repo' scope enabled.")
                print("1. Go to: https://github.com/settings/tokens")
                print("2. Generate a new token with the 'repo' scope")
                print("3. Run this script again with the new token")
        except Exception:
            pass

        with open(log_file, 'a') as log:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log.write(f"[FAILED] {owner}/{repo_name} - Error: {e}\n")
        return False, None

    except Exception as e:
        print(f"Unexpected error: {e}")
        with open(log_file, 'a') as log:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log.write(f"[ERROR] {owner}/{repo_name} - Unexpected error: {e}\n")
        return False, None


def main():
    """Main function to process repositories and fork them."""
    args = parse_arguments()

    # Check if YAML file exists
    if not os.path.isfile(args.file):
        print(f"Error: Repositories file '{args.file}' not found")
        sys.exit(1)

    # Initialize log file
    with open(args.log, 'w') as log:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"Fork operation started at {timestamp}\n")
        log.write("-----------------------------------\n")

    # Read repositories from YAML file
    data = read_yaml_file(args.file)

    # Check if the YAML has the expected structure
    if not data or 'repositories' not in data:
        print(
            "Error: Invalid YAML structure. The file should contain a 'repositories' list.")
        sys.exit(1)

    # Process each repository
    print("Starting to fork repositories...")
    for repo in data['repositories']:
        # Check if repository has required fields
        if 'owner' not in repo or 'name' not in repo:
            print("Warning: Skipping repository with missing owner or name")
            continue

        owner = repo['owner']
        name = repo['name']
        description = repo.get('description', '')

        # Fork the repository
        fork_repository(
            owner, name, description, args.token, args.org, args.log
        )

        # GitHub recommends waiting between API requests to avoid rate limiting
        time.sleep(2)

    print(f"Forking process completed. See {args.log} for details.")


if __name__ == "__main__":
    main()
