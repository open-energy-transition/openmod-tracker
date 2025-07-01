"""Get detailed information about GitHub users who interacted with a repository."""

import logging
from pathlib import Path
from time import time
from typing import Literal

import click
import pandas as pd
from github.GithubException import RateLimitExceededException

from .github_api import get_github_client, get_rate_limit_info

LOGGER = logging.getLogger(__name__)


def get_repo_users(
    repo: str,
    interaction_type: Literal["stargazers", "forks", "watchers", "issues", "pulls"],
    g=None,
) -> pd.DataFrame:
    """Get all users who interacted with a repo in a specific way using PyGithub."""
    if g is None:
        g = get_github_client()
    all_users = []
    try:
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
    except RateLimitExceededException:
        LOGGER.warning("Rate limit exceeded while fetching repo users.")
        time.sleep(60)
    if all_users:
        df = pd.DataFrame(all_users, columns=["username", "timestamp"])
        df["interaction"] = interaction_type
        df["repo"] = repo
        return df
    return pd.DataFrame()


def get_user_details(
    username: str, repos: set[str], wait: float = 0.0, g=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Get detailed information about a GitHub user using PyGithub.

    Args:
        username (str): The GitHub username.
        repos (set[str]): Set of repositories the user has interacted with.
        wait (float, optional): Seconds to wait before making the API call (for rate limiting). Defaults to 0.0.
        g (Github, optional): An authenticated PyGithub Github client. If None, a new client is created.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]:
            - user_df: DataFrame with user details (index=username).
            - orgs_df: DataFrame with organization descriptions (index=org login).
    """
    if g is None:
        g = get_github_client()
    if wait > 0:
        time.sleep(wait)
    try:
        user = g.get_user(username)
        user_data = {
            "name": user.name,
            "company": user.company,
            "blog": user.blog,
            "location": user.location,
            "email": user.email,
            "bio": user.bio,
            "twitter_username": user.twitter_username,
            "followers": user.followers,
            "following": user.following,
            "repos": ",".join(sorted(repos)),
        }
        # Get user's README
        try:
            readme = (
                g.get_repo(f"{username}/{username}")
                .get_readme()
                .decoded_content.decode()
            )
        except Exception:
            readme = ""
        user_data["readme"] = readme
        # Get user's organizations
        orgs = list(user.get_orgs())
        user_data["orgs"] = ",".join(org.login for org in orgs)
        orgs_df = pd.DataFrame(
            {"description": [org.description for org in orgs]},
            index=[org.login for org in orgs],
        )
        user_df = pd.DataFrame(user_data, index=[username])
        return user_df, orgs_df
    except RateLimitExceededException:
        LOGGER.warning("Rate limit exceeded while fetching user details.")
        time.sleep(60)
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        LOGGER.warning(f"Failed to fetch user details for {username}: {e}")
        return pd.DataFrame(), pd.DataFrame()


@click.command()
@click.option(
    "--user-interactions",
    type=click.Path(exists=True, path_type=Path),
    default="inventory/output/user_interactions.csv",
)
@click.option(
    "--outdir",
    type=click.Path(exists=False, dir_okay=True, file_okay=False, path_type=Path),
    default="inventory/output",
)
def cli(user_interactions: Path, outdir: Path):
    """CLI entry point to collect detailed user info for all users in user_interactions.csv using PyGithub.

    Args:
        user_interactions (Path): Path to the user_interactions.csv file (from get_repo_users.py).
        outdir (Path): Output directory for user_details.csv and organizations.csv.

    Output:
        Writes user_details.csv and organizations.csv to the output directory.
    """
    g = get_github_client()
    users_df = pd.read_csv(user_interactions)
    user_repo_map = users_df.groupby("username")["repo"].agg(lambda x: set(x)).to_dict()
    unique_users = list(user_repo_map.keys())
    LOGGER.info(f"Collecting details for {len(unique_users)} unique users")
    remaining, limit, reset = get_rate_limit_info(g)
    now = int(time())
    seconds_to_reset = max(reset - now, 1)
    wait_per_call = (
        max(seconds_to_reset / max(remaining, 1), 1)
        if remaining < len(unique_users)
        else 0
    )
    user_results = []
    org_results = []
    for i, username in enumerate(unique_users):
        user_df, org_df = get_user_details(
            username, user_repo_map[username], wait=wait_per_call, g=g
        )
        if not user_df.empty:
            user_results.append(user_df)
        if not org_df.empty:
            org_results.append(org_df)
    detailed_users_df = pd.concat(user_results) if user_results else pd.DataFrame()
    orgs_df = pd.concat(org_results) if org_results else pd.DataFrame()
    outdir.mkdir(parents=True, exist_ok=True)
    detailed_users_df.to_csv(outdir / "user_details.csv")
    orgs_df.to_csv(outdir / "organizations.csv")


if __name__ == "__main__":
    cli()
