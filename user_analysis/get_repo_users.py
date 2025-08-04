"""Get all users who interacted with a GitHub repository in various ways."""

import concurrent.futures
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import click
import pandas as pd
from github import Github
from github.Repository import Repository
from github_api import get_github_client, get_rate_limit_info
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)
COLS = ["username", "timestamp", "interaction", "repo"]


def get_repo_users(repo: str, gh_client: Github, threads: int = 4) -> pd.DataFrame:
    """Get all users who interacted with a repo in a specific way using PyGithub.

    Args:
        repo (str): The repository in 'owner/name' format.
        gh_client (Github): An authenticated PyGithub Github client.
        threads (int, optional): Number of threads over which to parallelise the tasks. Defaults to 5.

    Returns:
        pd.DataFrame: DataFrame with columns ['username', 'timestamp', 'interaction', 'repo'] for each user interaction.
    """
    repo_obj = gh_client.get_repo(repo)
    # Prepare function and args for parallel execution
    tasks = [_get_stargazer_users, _get_fork_users, _get_issue_users, _get_pull_users]
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        # Submit functions for execution
        results = [executor.submit(task, repo_obj) for task in tasks]

        all_users = [user for sublist in results for user in sublist.result()]

    if all_users:
        df = pd.DataFrame(all_users, columns=["username", "timestamp", "interaction"])
        df["repo"] = repo
        return df
    return pd.DataFrame()


def _get_stargazer_users(repo_obj: Repository) -> list[tuple[str, datetime, str]]:
    """Get all users who starred a repository with their star date."""
    stargazers = [
        (stargazer.user.login, stargazer.starred_at, "stargazer")
        for stargazer in repo_obj.get_stargazers_with_dates()
    ]
    return stargazers


def _get_fork_users(repo_obj: Repository) -> list[tuple[str, datetime, str]]:
    """Get all users who forked a repository with their fork date."""
    forkers = [
        (fork.owner.login, fork.created_at, "fork") for fork in repo_obj.get_forks()
    ]
    return forkers


def _get_issue_users(repo_obj: Repository) -> list[tuple[str, datetime, str]]:
    """Get all users who opened issues on a repository with their issue creation date."""
    issue_users = [
        (issue.user.login, issue.created_at, "issue")
        for issue in repo_obj.get_issues(state="all")
        if issue.user
    ]
    return issue_users


def _get_pull_users(repo_obj: Repository) -> list[tuple[str, datetime, str]]:
    """Get all users who opened pull requests on a repository with their PR creation date."""
    pr_users = [
        (pr.user.login, pr.created_at, "pull")
        for pr in repo_obj.get_pulls(state="all")
        if pr.user
    ]
    return pr_users


@click.command()
@click.option(
    "--stats-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to the CSV file containing repository URLs in the first column.",
    default="inventory/output/stats.csv",
)
@click.option(
    "--out-path",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
    help="Output path for the user interactions data file.",
    default="inventory/output/user_interactions.csv",
)
@click.option(
    "--threads",
    type=int,
    help="Number of threads over which to parallelise the tasks.",
    default=5,
)
def cli(stats_file: Path, out_path: Path, threads: int):
    """CLI entry point to collect all GitHub users who interact with the repositories listed in a stats file."""
    out_path.mkdir(parents=True, exist_ok=True)
    users_df = pd.DataFrame(columns=COLS, index=[])
    users_df.to_csv(out_path, index=False)

    gh_client = get_github_client()
    repos_df = pd.read_csv(stats_file, index_col=0)
    for repo_url in tqdm(repos_df.index, desc="Collecting users"):
        url_parts = urlparse(repo_url)
        if url_parts.netloc.endswith("github.com"):
            repo = url_parts.path.strip("/")
            LOGGER.warning(f"Collecting users for {repo}")
        else:
            LOGGER.warning(
                f"Skipping user collection for {repo_url} as it is not a GitHub repo."
            )
            continue

        df = get_repo_users(repo, gh_client, threads)
        if df.empty:
            LOGGER.warning(f"No users found for {repo}.")
            continue
        df[COLS].to_csv(out_path, mode="a", header=False, index=False)
        remaining_calls = get_rate_limit_info(gh_client)[0]
        LOGGER.warning(f"Remaining API calls: {remaining_calls}.")


if __name__ == "__main__":
    cli()
