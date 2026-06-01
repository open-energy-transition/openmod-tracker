# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Repository Interaction Collector.

This script fetches comprehensive repository interaction data from GitHub or GitLab
based on the repository URL, using the appropriate API client with rate limiting,
pagination, and error handling.
"""

import logging
from pathlib import Path
from urllib.parse import urlparse

import click
import pandas as pd
from github_api import GitHubRepositoryCollectorGH
from gitlab_api import GitLabRepositoryCollectorGL
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)

COLS = [
    "username",
    "interaction",
    "subtype",
    "number",
    "created",
    "closed",
    "merged",
    "repo",
]


def get_repo_and_host(url: str) -> str | None:
    """Extract the repository path and host from a URL.

    Args:
        url: Repository URL

    Returns:
        A tuple of (repository path, host) if the URL is recognized, otherwise None.
    """
    parsed = urlparse(url.lower())
    netloc = parsed.netloc
    path = parsed.path.strip("/")

    if netloc.endswith("github.com"):
        repo = "gh:" + path
    elif "gitlab" in netloc:
        repo = "gl:" + path
    else:
        LOGGER.warning(f"Skipping user collection for {url} - unknown host.")
        repo = None

    return repo


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
    default="user_analysis/output/repo_interactions.csv",
)
def cli(stats_file: Path, out_path: Path):
    """CLI entry point to collect all users who interact with repositories listed in a stats file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        existing_interactions = pd.read_csv(out_path)
    else:
        existing_interactions = pd.DataFrame(columns=COLS, index=[])
        existing_interactions.to_csv(out_path, index=False)

    repos_df = pd.read_csv(stats_file, index_col="id")

    # Initialize collectors
    github_collector = GitHubRepositoryCollectorGH()
    gitlab_collector = GitLabRepositoryCollectorGL()
    host_repos = repos_df["html_url"].apply(get_repo_and_host).dropna().values
    existing_interactions = existing_interactions[
        existing_interactions.repo.isin(host_repos)
    ]
    for host_repo in tqdm(host_repos, desc="Collecting users"):
        host, repo_path = host_repo.split(":", 1)

        LOGGER.warning(f"Collecting users for {repo_path} from {host}")

        # Route to appropriate collector
        if host == "gh":
            df = github_collector.collect_repo_data(repo_path)
        elif host == "gl":
            df = gitlab_collector.collect_repo_data(repo_path)
        else:
            LOGGER.warning(f"Unsupported host: {host}")
            continue

        if df.empty:
            LOGGER.warning(f"No users found for {repo_path}.")
            continue

        existing_interactions = pd.concat([existing_interactions, df]).reindex(
            columns=COLS
        )

        # Clean up data by removing data that has been downloaded already
        # and merging rows with updated data (e.g. issues/PRs that have since been closed/merged)
        is_repo = existing_interactions["repo"] == repo_path
        no_dups_interactions = (
            existing_interactions[is_repo]
            .groupby(
                ["username", "interaction", "subtype", "number", "repo"],
                group_keys=False,
                dropna=False,
            )
            .apply(lambda x: x.ffill().bfill())
            .drop_duplicates()
            .dropna(subset=["username", "created", "repo"])
        )
        existing_interactions = pd.concat(
            [existing_interactions[~is_repo], no_dups_interactions]
        )
        existing_interactions["number"] = existing_interactions["number"].astype(
            "Int32"
        )
        existing_interactions.drop_duplicates().sort_values(["repo", "created"]).to_csv(
            out_path, index=False
        )


if __name__ == "__main__":
    cli()
