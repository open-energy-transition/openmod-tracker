# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""GitHub API utility functions for repository management.

This module provides a class to interact with the GitHub API,
including forking repositories, syncing forks, and retrieving
repository details.
"""

import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Literal

import dotenv
import git
from github import Github
from github.GithubException import GithubException
from github.Repository import Repository
from util import set_logging_handlers

# Set up module logger
LOGGER = logging.getLogger(__name__)
set_logging_handlers(LOGGER, log_file=None)

dotenv.load_dotenv()


class GitAPI:
    """GitHub API wrapper class for repository management.

    This class provides methods to interact with the GitHub API for
    operations like forking repositories, syncing forks, and retrieving
    repository details.
    """

    def __init__(self, org: str):
        """Initialize the GitHub API client.

        Args:
            org (str): GitHub organization.
        """
        self.org = org

        self.github_client = Github(os.environ["GITHUB_TOKEN"])
        self.org_obj = self.github_client.get_organization(org)
        self.repos = {repo.name: repo for repo in self.org_obj.get_repos()}

    def check_existing_fork(self, upstream_owner: str, repo_name: str) -> bool:
        """Check if the repository is already forked by the organization.

        Args:
            upstream_owner (str): Owner of the original repository
            repo_name (str): Name of the repository

        Returns:
            bool: True if the fork exists, False otherwise
        """
        repo = self.repos.get(repo_name, None)
        upstream_fullname = f"{upstream_owner}/{repo_name}"
        if repo is not None:
            if (
                repo.fork
                and (repo.source.full_name == upstream_fullname)
                # To catch edge cases where the repo is a fork of a fork.
                # We check for the intermediate source in the base source's forks:
                or any(
                    repo.full_name == upstream_fullname
                    for repo in self.github_client.get_repo(
                        repo.source.full_name
                    ).get_forks()
                )
            ):
                exists = True
            else:
                raise GithubException(
                    1,
                    message=f"Found a repo with the same name ({repo_name}) but different source. "
                    f"Received {repo.source.full_name}, expected {upstream_owner}/{repo_name}",
                )
        else:
            # Repository doesn't exist in the organization
            LOGGER.info(f"Repository {repo_name} not found in organization {self.org}")
            exists = False

        return exists

    def sync_fork(self, owner: str, repo_name: str, branch: str) -> bool:
        """Sync a fork with its upstream repository.

        Args:
            owner (str): Owner of the original repository
            repo_name (str): Name of the repository
            branch (str): Branch to sync (usually 'main' or 'master')

        Returns:
            bool: True if sync was successful, False otherwise
        """
        LOGGER.info(
            f"Syncing {self.org}/{repo_name} with upstream {owner}/{repo_name}..."
        )

        try:
            fork_repo = self.org_obj.get_repo(repo_name)

            # Use the merge upstream API
            result = fork_repo.merge_upstream(branch)

            # Check if merge was successful
            if result:
                merged = True
                if hasattr(result, "commits"):
                    for commit in result.commits:
                        if hasattr(commit, "status") and commit.status == "error":
                            merged = False
                            break

                if merged:
                    LOGGER.info(
                        f"{self.org}/{repo_name} synced with {owner}/{repo_name}"
                    )
                    # Get branches from the result object and log them
                    base_branch = getattr(result, "base_branch", None)
                    head_branch = getattr(result, "head_branch", None)
                    LOGGER.info(f"  Merged {head_branch} into {base_branch}\n")
                    return True
                else:
                    LOGGER.error(f"{self.org}/{repo_name} sync failed")
                    return False
            else:
                LOGGER.info(
                    f"{self.org}/{repo_name} already in sync with {owner}/{repo_name}"
                )
                return True

        except GithubException as e:
            LOGGER.error(
                f"{self.org}/{repo_name} sync with {owner}/{repo_name} failed: {e}"
            )
            return False

        except Exception as e:
            LOGGER.error(f"{self.org}/{repo_name} - Unexpected error: {e}")
            return False

    def get_repository_details(self, repo_name):
        """Get details of a repository.

        Args:
            repo_name (str): Name of the repository

        Returns:
            github.Repository.Repository: Repository object or None if not
                found
        """
        try:
            # Get the repository using the owner/name format
            return self.github_client.get_repo(f"{self.org}/{repo_name}")
        except GithubException as e:
            LOGGER.error(f"Error getting repository details: {e}")
            return None
        except Exception as e:
            LOGGER.error(f"Unexpected error getting repository details: {e}")
            return None

    def fork_repository(self, source_owner, repo_name):
        """Fork a GitHub repository using the GitHub API.

        Args:
            source_owner (str): Owner of the original repository
            repo_name (str): Name of the repository

        Returns:
            tuple: (success, fork_url)
                - success (bool): True if fork operation was successful
                - fork_url (str): URL of the forked repository if successful,
                                None otherwise
        """
        try:
            source_repo = self.github_client.get_repo(f"{source_owner}/{repo_name}")

            fork = source_repo.create_fork(self.org_obj)

            LOGGER.info(f"Successfully forked {source_owner}/{repo_name} to {self.org}")
            LOGGER.info(f"Fork URL: {fork.html_url}")

            return True, fork.html_url

        except GithubException as e:
            LOGGER.error(f"Failed to fork {source_owner}/{repo_name}: {e}")

            if e.status == 403:  # Forbidden
                sys.exit(1)

            return False, None

        except Exception as e:
            LOGGER.error(f"Unexpected error: {e}")
            return False, None

    def create_repository(self, upstream_url: str, name: str):
        """Create a new repository in the organization.

        Args:
            upstream_url (str): URL of the upstream repository to clone
            name (str): Name of the new repository
        """
        LOGGER.info(f"Creating new repository {name} in organization {self.org}...")
        self.org_obj.create_repo(
            name,
            allow_rebase_merge=True,
            auto_init=False,
            description=f"Clone of {upstream_url}",
            has_issues=False,
            has_projects=False,
            has_wiki=False,
            private=False,
        )

    def process_non_github_url(
        self, url: str, destination_org: str, repo_name: str
    ) -> Literal["forked", "synced", "sync failed", "fork failed"]:
        """Fork a non-GitHub repository by cloning and pushing to a new GitHub repo.

        Args:
            url (str): URL of the non-GitHub repository to clone
            destination_org (str): GitHub organization to push the new repository to
            repo_name (str): Name of the new repository to create in the organization
        Returns:
            str: Result of the operation: "forked", "synced", "sync failed", or "fork failed"
        """
        result: Literal["forked", "synced", "sync failed", "fork failed"]
        if "/" in repo_name:
            raise ValueError(
                f"Repository name should not contain '/' character. Received {repo_name}"
            )
        with tempfile.TemporaryDirectory() as tmpdirname:
            repo_dir = Path(tmpdirname) / repo_name
            try:
                LOGGER.info(f"Cloning non-GitHub repository from {url}...")
                git.Repo.clone_from(url, repo_dir)
                repo = self.repos.get(repo_name, None)
                if repo is None:
                    self.create_repository(url, repo_name)
                    time.sleep(30)  # Wait for the repository to be fully created
                    success = "forked"
                elif repo.fork:
                    raise GithubException(
                        1,
                        message="Repository already exists as a fork from another source",
                    )
                else:
                    success = "synced"
            except (git.exc.GitCommandError, GithubException) as e:
                LOGGER.error(f"Failed to clone repository from {url}: {e}")
                result = "fork failed"

            try:
                remote_repo = self.org_obj.get_repo(repo_name)
                local_repo = git.Repo(repo_dir)
                self._push_to_origin(remote_repo, local_repo)
                LOGGER.info(
                    f"Successfully pushed {url} to new repository {remote_repo.html_url}"
                )
                result = success
            except GithubException as e:
                LOGGER.error(
                    f"Failed to get created repository {repo_name} in organization {destination_org}: {e}"
                )
            except git.exc.GitCommandError as e:
                LOGGER.error(
                    f"Failed to push to repository {repo_name} in organization {destination_org}: {e}"
                )
                too_large = []
                for file in repo_dir.rglob("*"):
                    filesize = file.stat().st_size
                    file_rel = file.relative_to(repo_dir)
                    if filesize > 100 * 1024 * 1024:
                        too_large.append(file_rel)
                if too_large:
                    LOGGER.error(
                        f"Repository contains {len(too_large)} files that are too large to push to github"
                    )
                result = "sync failed"
        return result

    def _push_to_origin(self, remote_repo: Repository, local_repo: git.Repo):
        """Push local changes to the remote repository.

        Args:
            remote_repo (Repository): The remote GitHub repository.
            local_repo (git.Repo): The local Git repository.
        """
        local_repo.delete_remote(local_repo.remotes.origin)
        origin = local_repo.create_remote(
            "origin",
            remote_repo.clone_url.replace(
                "https://", f"https://{os.environ['GITHUB_TOKEN']}@"
            ),
        )
        with local_repo.config_writer() as config:
            config.set_value("http", "postBuffer", 157286400)
            origin.push(refspec="HEAD:refs/heads/main", force=True)
