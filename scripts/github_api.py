import os
import datetime
from github import Github
from github.GithubException import GithubException
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_ORG = os.getenv('GITHUB_ORG', 'openmod-tracker')

# Initialize the GitHub client
_github_client = None


def get_github_client():
    """
    Get or create a GitHub client instance.

    Returns:
        Github: A GitHub client instance
    """
    global _github_client
    if _github_client is None:
        _github_client = Github(GITHUB_TOKEN)
    return _github_client


def check_existing_fork(owner, repo_name, org=None):
    """
    Check if the repository is already forked by the organization.

    Args:
        owner (str): Owner of the original repository
        repo_name (str): Name of the repository
        org (str, optional): Organization to check for fork.
                            Defaults to GITHUB_ORG.

    Returns:
        bool: True if the fork exists, False otherwise
    """
    organization = org or GITHUB_ORG
    github = get_github_client()

    try:
        # Get the organization
        org_obj = github.get_organization(organization)

        try:
            fork_repo = org_obj.get_repo(repo_name)

            if fork_repo.fork:
                source_repo = fork_repo.source
                if source_repo.full_name == f"{owner}/{repo_name}":
                    return True
        except GithubException:
            # Repository doesn't exist in the organization
            print(f"Repository {repo_name} not found in organization {organization}")
            pass

        return False
    except Exception as e:
        print(f"Error checking existing fork: {e}")
        return False


def sync_fork(owner, repo_name, branch, org=None, log_file=None):
    """
    Sync a fork with its upstream repository.

    Args:
        owner (str): Owner of the original repository
        repo_name (str): Name of the repository
        branch (str): Branch to sync
        org (str, optional): Organization containing the fork.
                            Defaults to GITHUB_ORG.
        log_file (str, optional): Path to log file for recording results.

    Returns:
        bool: True if sync was successful, False otherwise
    """
    organization = org or GITHUB_ORG
    github = get_github_client()

    print(f"Syncing {organization}/{repo_name} with upstream "
          f"{owner}/{repo_name}...")

    try:
        fork_repo = None
        try:
            org_obj = github.get_organization(organization)
            fork_repo = org_obj.get_repo(repo_name)
        except GithubException as e:
            print(f"Error getting fork repository: {e}")
            if log_file:
                with open(log_file, 'a') as log:
                    timestamp = datetime.datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    log.write(
                        f"[SYNC-FAILED] {organization}/{repo_name} sync with "
                        f"{owner}/{repo_name} failed: {e}\n"
                    )
            return False

        # Use the merge upstream API
        result = fork_repo.merge_upstream(branch)

        # Check if merge was successful
        if result:
            merged = True
            if hasattr(result, 'commits'):
                for commit in result.commits:
                    if hasattr(commit, 'status') and commit.status == 'error':
                        merged = False
                        break

            if merged:
                print(f"Successfully synced {organization}/{repo_name} with "
                      f"upstream {owner}/{repo_name}")
                if log_file:
                    with open(log_file, 'a') as log:
                        timestamp = datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        log.write(
                            f"[SYNC] {organization}/{repo_name} synced with "
                            f"{owner}/{repo_name} at {timestamp}\n"
                        )
                        # Get branches from the result object
                        base_branch = getattr(result, 'base_branch', None)
                        head_branch = getattr(result, 'head_branch', None)
                        if base_branch and head_branch:
                            log.write(
                                f"  Merged {head_branch} into "
                                f"{base_branch}\n"
                            )
                return True
            else:
                print(f"Failed to sync {organization}/{repo_name}")
                if log_file:
                    with open(log_file, 'a') as log:
                        timestamp = datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        log.write(
                            f"[SYNC-FAILED] {organization}/{repo_name} "
                            f"sync failed\n"
                        )
                return False
        else:
            print(f"Fork {organization}/{repo_name} is already up to date")
            if log_file:
                with open(log_file, 'a') as log:
                    timestamp = datetime.datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    log.write(
                        f"[UP-TO-DATE] {organization}/{repo_name} "
                        f"already in sync with {owner}/{repo_name} "
                        f"at {timestamp}\n"
                    )
            return True

    except GithubException as e:
        print(f"GitHub API error syncing {organization}/{repo_name}: {e}")
        if log_file:
            with open(log_file, 'a') as log:
                timestamp = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                log.write(
                    f"[SYNC-FAILED] {organization}/{repo_name} sync with "
                    f"{owner}/{repo_name} failed: {e}\n"
                )
        return False

    except Exception as e:
        print(f"Unexpected error syncing {organization}/{repo_name}: {e}")
        if log_file:
            with open(log_file, 'a') as log:
                timestamp = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                log.write(
                    f"[SYNC-ERROR] {organization}/{repo_name} - "
                    f"Unexpected error: {e}\n"
                )
        return False


def get_repository_details(owner, repo_name, org=None):
    """
    Get details of a repository.

    Args:
        owner (str): Owner of the repository
        repo_name (str): Name of the repository
        org (str, optional): Organization if different from owner.
                             Defaults to None.

    Returns:
        github.Repository.Repository: Repository object or None if not found
    """
    repo_owner = org or owner
    github = get_github_client()

    try:
        # Get the repository
        if org:
            # If an organization is specified, get the repo from the org
            org_obj = github.get_organization(repo_owner)
            return org_obj.get_repo(repo_name)
        else:
            # Otherwise get the repo from the user
            return github.get_repo(f"{repo_owner}/{repo_name}")
    except GithubException as e:
        print(f"Error getting repository details: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error getting repository details: {e}")
        return None


def fork_repository(owner, repo_name, org=None, description=None):
    """
    Fork a GitHub repository using the GitHub API.

    Args:
        owner (str): Owner of the original repository
        repo_name (str): Name of the repository
        org (str, optional): Organization to fork to. Defaults to GITHUB_ORG.
        description (str, optional): Description for the forked repository.

    Returns:
        tuple: (success, fork_url)
            - success (bool): True if fork operation was successful
            - fork_url (str): URL of the forked repository if successful,
                             None otherwise
    """
    organization = org or GITHUB_ORG
    github = get_github_client()

    try:
        source_repo = github.get_repo(f"{owner}/{repo_name}")

        org_obj = github.get_organization(organization)

        fork = source_repo.create_fork(org_obj)

        print(f"Successfully forked {owner}/{repo_name} to {organization}")
        print(f"Fork URL: {fork.html_url}")

        return True, fork.html_url

    except GithubException as e:
        print(f"Failed to fork {owner}/{repo_name}: {e}")

        if e.status == 403:  # Forbidden
            print("\nERROR: Your GitHub token doesn't have the necessary"
                  " permissions.")
            print("You need to create a new token with the 'repo' scope"
                  " enabled.")
            print("1. Go to: https://github.com/settings/tokens")
            print("2. Generate a new token with the 'repo' scope")
            print("3. Set the token in your .env file as GITHUB_TOKEN")

        return False, None

    except Exception as e:
        print(f"Unexpected error: {e}")
        return False, None
