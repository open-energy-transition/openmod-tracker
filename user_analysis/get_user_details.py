# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Get detailed information about GitHub users who interacted with a repository."""

import logging
import time
from pathlib import Path

import click
import pandas as pd
from github import Github
from github.GithubException import GithubException, RateLimitExceededException
from github_api import get_github_client, get_rate_limit_info
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)

USER_COLS = [
    "company",
    "blog",
    "location",
    "email_domain",
    "bio",
    "twitter_username",
    "followers",
    "following",
    "repos",
    "readme",
    "orgs",
]
ORG_COLS = ["description"]


def get_user_details(
    username: str, repos: set[str], gh_client: Github, wait: float = 0.0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Get detailed information about a GitHub user using PyGithub.

    Args:
        username (str): The GitHub username.
        repos (set[str]): Set of repositories the user has interacted with.
        wait (float, optional):
            Seconds to wait before making the API call (for rate limiting).
            Defaults to 0.0.
        gh_client (Github): An authenticated PyGithub Github client.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]:
            - user_df: DataFrame with user details (index=username).
            - orgs_df: DataFrame with organization descriptions (index=org login).
    """
    if wait > 0:
        time.sleep(wait)
    try:
        user = gh_client.get_user(username)
        user_data = {
            "company": user.company,
            "blog": user.blog,
            "location": user.location,
            "email_domain": user.email.split("@")[1] if user.email else None,
            "bio": user.bio,
            "twitter_username": user.twitter_username,
            "followers": user.followers,
            "following": user.following,
            "repos": ",".join(sorted(repos)),
        }
        # Get user's README
        try:
            readme = (
                gh_client.get_repo(f"{username}/{username}")
                .get_readme()
                .decoded_content.decode()
            )
        except GithubException:
            readme = ""
        user_data["readme"] = readme.strip()
        # Get user's organizations
        orgs = list(user.get_orgs())
        user_data["orgs"] = ",".join(org.login for org in orgs)
        orgs_df = pd.DataFrame(
            {"description": [org.description.strip() for org in orgs]},
            index=pd.Index([org.login for org in orgs], name="orgname"),
        )
        user_df = pd.DataFrame(user_data, index=pd.Index([username], name="username"))
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
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
    help="Path to the user_interactions.csv file (from get_repo_users.py).",
    default="user_analysis/output/user_interactions.csv",
)
@click.option(
    "--outdir",
    type=click.Path(exists=False, dir_okay=True, file_okay=False, path_type=Path),
    help="Output directory for user_details.csv and organizations.csv.",
    default="user_analysis/output",
)
@click.option(
    "--refresh-cache",
    help="If True, collect all user data from scratch rather than appending to the existing user details table.",
    is_flag=True,
)
def cli(user_interactions: Path, outdir: Path, refresh_cache: bool):
    """CLI entry point to collect detailed user info for all users in user_interactions.csv using PyGithub."""
    outdir.mkdir(parents=True, exist_ok=True)
    user_details_path = outdir / "user_details.csv"
    org_details_path = outdir / "organizations.csv"

    if user_details_path.exists() and not refresh_cache:
        existing_users = pd.read_csv(user_details_path, index_col=0)
    else:
        existing_users = pd.DataFrame(columns=USER_COLS, index=[])
        existing_users.to_csv(user_details_path)

    if org_details_path.exists() and not refresh_cache:
        existing_orgs = pd.read_csv(org_details_path, index_col=0)
    else:
        existing_orgs = pd.DataFrame(columns=ORG_COLS, index=[])
        existing_orgs.to_csv(org_details_path)

    gh_client = get_github_client()
    users_df = pd.read_csv(user_interactions)
    users_df = users_df[~users_df.username.isin(existing_users.index)]
    user_repo_map = users_df.groupby("username")["repo"].agg(lambda x: set(x)).to_dict()

    LOGGER.warning(f"Collecting details for {len(user_repo_map)} unique users")

    for username, repos in tqdm(user_repo_map.items(), desc="Collecting user details"):
        user_df, org_df = get_user_details(username, repos, gh_client, wait=0)
        remaining_calls = get_rate_limit_info(gh_client)[0]
        LOGGER.warning(f"Remaining API calls: {remaining_calls}.")
        # Only add new orgs
        org_df = org_df.drop(existing_orgs.index, axis=0, errors="ignore")
        if not user_df.empty:
            user_df[USER_COLS].to_csv(user_details_path, mode="a", header=False)
        if not org_df.empty:
            org_df[ORG_COLS].to_csv(org_details_path, mode="a", header=False)


if __name__ == "__main__":
    cli()
