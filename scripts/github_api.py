"""GitHub API utility functions for repository management.

This module provides a class to interact with the GitHub API,
including forking repositories, syncing forks, and retrieving
repository details.
"""

import logging
from github import Github
from github.GithubException import GithubException
from util import log_to_file

# Set up module logger
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
LOGGER.addHandler(console_handler)

DEFAULT_ORG = "openmod-tracker"


class GitHubAPI:
    """GitHub API wrapper class for repository management.

    This class provides methods to interact with the GitHub API for
    operations like forking repositories, syncing forks, and retrieving
    repository details.
    """

    def __init__(self, token=None, org=None):
        """Initialize the GitHub API client.

        Args:
            token (str, optional): GitHub API token.
            org (str, optional): GitHub organization. Defaults to DEFAULT_ORG.
        """
        self.token = token
        self.org = org or DEFAULT_ORG
        self._github_client = None

    @property
    def github_client(self):
        """Get or create a GitHub client instance.

        Returns:
            Github: A GitHub client instance
        """
        if self._github_client is None:
            self._github_client = Github(self.token)
        return self._github_client

    def check_existing_fork(self, owner, repo_name, org=None):
        """Check if the repository is already forked by the organization.

        Args:
            owner (str): Owner of the original repository
            repo_name (str): Name of the repository
            org (str, optional): Organization to check for fork.
                                Defaults to self.org.

        Returns:
            bool: True if the fork exists, False otherwise
        """
        organization = org or self.org

        try:
            # Get the organization
            org_obj = self.github_client.get_organization(organization)

            try:
                fork_repo = org_obj.get_repo(repo_name)

                if fork_repo.fork:
                    source_repo = fork_repo.source
                    if source_repo.full_name == f"{owner}/{repo_name}":
                        return True
            except GithubException:
                # Repository doesn't exist in the organization
                LOGGER.info(
                    f"Repository {repo_name} not found in "
                    f"organization {organization}"
                )
                pass

            return False
        except Exception as e:
            LOGGER.error(f"Error checking existing fork: {e}")
            return False

    def sync_fork(self, owner, repo_name, branch, org=None, log_file=None):
        """Sync a fork with its upstream repository.

        Args:
            owner (str): Owner of the original repository
            repo_name (str): Name of the repository
            branch (str): Branch to sync
            org (str, optional): Organization containing the fork.
                                Defaults to self.org.
            log_file (str, optional): Path to log file for recording results.

        Returns:
            bool: True if sync was successful, False otherwise
        """
        organization = org or self.org

        LOGGER.info(
            f"Syncing {organization}/{repo_name} with upstream "
            f"{owner}/{repo_name}..."
        )

        try:
            fork_repo = None
            try:
                org_obj = self.github_client.get_organization(organization)
                fork_repo = org_obj.get_repo(repo_name)
            except GithubException as e:
                LOGGER.error(f"Error getting fork repository: {e}")
                log_to_file(
                    log_file,
                    "SYNC-FAILED",
                    f"{organization}/{repo_name} sync with "
                    f"{owner}/{repo_name} failed: {e}"
                )
                return False

            # Use the merge upstream API
            result = fork_repo.merge_upstream(branch)

            # Check if merge was successful
            if result:
                merged = True
                if hasattr(result, "commits"):
                    for commit in result.commits:
                        if (hasattr(commit, "status")
                                and commit.status == "error"):
                            merged = False
                            break

                if merged:
                    LOGGER.info(
                        f"Successfully synced {organization}/{repo_name} with "
                        f"upstream {owner}/{repo_name}"
                    )
                    log_to_file(
                        log_file,
                        "SYNC",
                        f"{organization}/{repo_name} synced with "
                        f"{owner}/{repo_name}"
                    )
                    # Get branches from the result object and log them
                    base_branch = getattr(result, "base_branch", None)
                    head_branch = getattr(result, "head_branch", None)
                    if log_file and base_branch and head_branch:
                        with open(log_file, "a") as log:
                            log.write(
                                f"  Merged {head_branch} into {base_branch}\n"
                            )
                    return True
                else:
                    LOGGER.error(f"Failed to sync {organization}/{repo_name}")
                    log_to_file(
                        log_file,
                        "SYNC-FAILED",
                        f"{organization}/{repo_name} sync failed"
                    )
                    return False
            else:
                LOGGER.info(
                    f"Fork {organization}/{repo_name} is already up to date"
                )
                log_to_file(
                    log_file,
                    "UP-TO-DATE",
                    f"{organization}/{repo_name} already in sync with "
                    f"{owner}/{repo_name}"
                )
                return True

        except GithubException as e:
            LOGGER.error(
                f"GitHub API error syncing {organization}/{repo_name}: {e}"
            )
            log_to_file(
                log_file,
                "SYNC-FAILED",
                f"{organization}/{repo_name} sync with "
                f"{owner}/{repo_name} failed: {e}"
            )
            return False

        except Exception as e:
            LOGGER.error(
                f"Unexpected error syncing {organization}/{repo_name}: {e}"
            )
            log_to_file(
                log_file,
                "SYNC-ERROR",
                f"{organization}/{repo_name} - Unexpected error: {e}"
            )
            return False

    def get_repository_details(self, owner, repo_name):
        """Get details of a repository.

        Args:
            owner (str): Owner of the repository (user or organization)
            repo_name (str): Name of the repository

        Returns:
            github.Repository.Repository: Repository object or None if not
                found
        """
        try:
            # Get the repository using the owner/name format
            return self.github_client.get_repo(f"{owner}/{repo_name}")
        except GithubException as e:
            LOGGER.error(f"Error getting repository details: {e}")
            return None
        except Exception as e:
            LOGGER.error(f"Unexpected error getting repository details: {e}")
            return None

    def fork_repository(
            self, source_owner, repo_name,
            destination_org=None
    ):
        """Fork a GitHub repository using the GitHub API.

        Args:
            source_owner (str): Owner of the original repository
            repo_name (str): Name of the repository
            destination_org (str, optional): Organization to fork to.
                                           Defaults to self.org.

        Returns:
            tuple: (success, fork_url)
                - success (bool): True if fork operation was successful
                - fork_url (str): URL of the forked repository if successful,
                                None otherwise
        """
        organization = destination_org or self.org

        try:
            source_repo = self.github_client.get_repo(
                f"{source_owner}/{repo_name}"
            )

            org_obj = self.github_client.get_organization(organization)

            fork = source_repo.create_fork(org_obj)

            LOGGER.info(
                f"Successfully forked {source_owner}/{repo_name} "
                f"to {organization}"
            )
            LOGGER.info(f"Fork URL: {fork.html_url}")

            return True, fork.html_url

        except GithubException as e:
            LOGGER.error(f"Failed to fork {source_owner}/{repo_name}: {e}")

            if e.status == 403:  # Forbidden
                LOGGER.error(
                    "\nERROR: Your GitHub token doesn't have the necessary "
                    "permissions."
                )

            return False, None

        except Exception as e:
            LOGGER.error(f"Unexpected error: {e}")
            return False, None
