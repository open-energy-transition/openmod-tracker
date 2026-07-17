# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Get detailed information about users who interacted with a repository."""

import logging
from pathlib import Path

import click
import pandas as pd
from github_api import GitHubClientGH, get_user_details_gh
from gitlab_api import GitLabClientGL, get_user_details_gl
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


@click.command()
@click.option(
    "--repo-interactions",
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
    help="Path to the repo_interactions.csv file (from get_repo_users.py).",
    default="user_analysis/output/repo_interactions.csv",
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
def cli(repo_interactions: Path, outdir: Path, refresh_cache: bool):
    """CLI entry point to collect detailed user info for all users in repo_interactions.csv."""
    outdir.mkdir(parents=True, exist_ok=True)
    user_details_path = outdir / "user_details.csv"
    org_details_path = outdir / "organizations.csv"

    if user_details_path.exists() and not refresh_cache:
        existing_users = pd.read_csv(user_details_path, index_col=0)
    else:
        existing_users = pd.DataFrame(columns=USER_COLS, index=[])

    if org_details_path.exists() and not refresh_cache:
        existing_orgs = pd.read_csv(org_details_path, index_col=0)
    else:
        existing_orgs = pd.DataFrame(columns=ORG_COLS, index=[])

    # Initialize clients
    gh_client = GitHubClientGH()
    gl_client = GitLabClientGL()

    users_df = pd.read_csv(repo_interactions)

    # Filter out any users for which we're removed the repo they are interacting with + any orgs that now disappear.
    # This ensures we don't have user/org details for users who no longer interact with any repos in our dataset.
    existing_users_start = existing_users[existing_users.index.isin(users_df.username)]
    existing_users_start = existing_users_start[
        existing_users_start.repos.notna() & (existing_users_start.repos != "")
    ]
    existing_users_start.to_csv(user_details_path)
    avail_orgs = set(",".join(existing_users_start.orgs.dropna()).split(","))
    existing_orgs_start = existing_orgs[existing_orgs.index.isin(avail_orgs)]
    existing_orgs_start.to_csv(org_details_path)

    # Filter out users we've already processed
    users_df = users_df[~users_df.username.isin(existing_users.index)]
    hosts = users_df["repo"].str.split(":", n=1, expand=True)[0]
    user_repo_map = users_df.groupby(["username", hosts])["repo"].agg(set).to_dict()

    LOGGER.warning(
        f"Collecting details for {len(user_repo_map)} unique user-host pairs"
    )

    for (username, host), repos in tqdm(
        user_repo_map.items(), desc="Collecting user details"
    ):
        # Route to appropriate API based on host
        if host == "gh":
            user_df, org_df = get_user_details_gh(username, repos, gh_client, wait=0)
            remaining_calls = gh_client.get_rate_limit_info()[0]
            LOGGER.warning(f"Remaining GitHub API calls: {remaining_calls}.")
        elif host == "gl":
            user_df = get_user_details_gl(username, repos, gl_client)
            org_df = pd.DataFrame()  # GitLab user details don't include orgs
        else:
            LOGGER.warning(f"Unsupported host '{host}' for user {username}")
            continue

        # Only add new orgs
        org_df = org_df[~org_df.index.isin(existing_orgs.index)]
        if not user_df.empty:
            # Ensure all columns exist, fill missing with None
            for col in USER_COLS:
                if col not in user_df:
                    user_df[col] = None
            # Drop users with no associated repos, since these can't be filtered by repo/tool downstream.
            user_df = user_df[user_df.repos.notna() & (user_df.repos != "")]
        if not user_df.empty:
            user_df[USER_COLS].to_csv(user_details_path, mode="a", header=False)
        if not org_df.empty:
            org_df[ORG_COLS].to_csv(org_details_path, mode="a", header=False)


if __name__ == "__main__":
    cli()
