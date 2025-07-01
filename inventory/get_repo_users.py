"""Get all users who interacted with a GitHub repository in various ways."""

import logging
from pathlib import Path

import click
import pandas as pd

from .github_api import get_github_client

LOGGER = logging.getLogger(__name__)


def get_repo_users(repo: str, interaction_type: str, g=None) -> pd.DataFrame:
    """Get all users who interacted with a repo in a specific way using PyGithub.

    Args:
        repo (str): The repository in 'owner/name' format.
        interaction_type (str): One of 'stargazers', 'forks', 'watchers', 'issues', 'pulls'.
        g (Github, optional): An authenticated PyGithub Github client. If None, a new client is created.

    Returns:
        pd.DataFrame: DataFrame with columns ['username', 'timestamp', 'interaction', 'repo'] for each user interaction.
    """
    if g is None:
        g = get_github_client()
    all_users = []
    repo_obj = g.get_repo(repo)
    if interaction_type == "stargazers":
        for user in repo_obj.get_stargazers_with_dates():
            all_users.append((user.user.login, user.starred_at))
    elif interaction_type == "forks":
        for fork in repo_obj.get_forks():
            all_users.append((fork.owner.login, fork.created_at))
    elif interaction_type == "watchers":
        for user in repo_obj.get_watchers():
            all_users.append((user.login, None))
    elif interaction_type == "issues":
        for issue in repo_obj.get_issues(state="all"):
            if issue.user:
                all_users.append((issue.user.login, issue.created_at))
    elif interaction_type == "pulls":
        for pr in repo_obj.get_pulls(state="all"):
            if pr.user:
                all_users.append((pr.user.login, pr.created_at))
    if all_users:
        df = pd.DataFrame(all_users, columns=["username", "timestamp"])
        df["interaction"] = interaction_type
        df["repo"] = repo
        return df
    return pd.DataFrame()


@click.command()
@click.option(
    "--stats-file",
    type=click.Path(exists=True, path_type=Path),
    default="inventory/output/stats.csv",
)
@click.option(
    "--outdir",
    type=click.Path(exists=False, dir_okay=True, file_okay=False, path_type=Path),
    default="inventory/output",
)
def cli(stats_file: Path, outdir: Path):
    """CLI entry point to collect all GitHub users who interact with the repositories listed in a stats file.

    Args:
        stats_file (Path): Path to the CSV file containing repository URLs in the first column.
        outdir (Path): Output directory for the user_interactions.csv file.

    Output:
        Writes user_interactions.csv to the output directory, containing all user interactions for each repo.
    """
    g = get_github_client()
    repos_df = pd.read_csv(stats_file, header=None)
    repo_urls = repos_df.iloc[:, 0].tolist()
    users_df = pd.DataFrame()
    for repo_url in repo_urls:
        if repo_url.startswith("https://github.com/"):
            repo = repo_url.replace("https://github.com/", "")
        else:
            continue
        LOGGER.info(f"Collecting users for {repo}")
        for interaction_type in ["stargazers", "forks", "watchers", "issues", "pulls"]:
            df = get_repo_users(repo, interaction_type, g=g)
            users_df = pd.concat([users_df, df])
    outdir.mkdir(parents=True, exist_ok=True)
    users_df.to_csv(outdir / "user_interactions.csv", index=False)


if __name__ == "__main__":
    cli()
