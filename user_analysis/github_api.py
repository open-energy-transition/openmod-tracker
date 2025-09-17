# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Authenticated GitHub API client using PyGithub."""

import logging
import os
import time

from dotenv import load_dotenv
from github import Github

load_dotenv()
LOGGER = logging.getLogger(__name__)


def get_github_client() -> Github:
    """Get an authenticated PyGithub Github client using the GITHUB_TOKEN environment variable.

    Returns:
        Github: An authenticated PyGithub Github client (or unauthenticated if no token is set).
    """
    return Github(os.environ.get("GITHUB_TOKEN", None))


def get_rate_limit_info(gh_client: Github) -> tuple[int, int, int]:
    """Get the current GitHub API rate limit status for the core resource.

    Args:
        gh_client (Github): An authenticated PyGithub Github client.

    Returns:
        tuple: (remaining, limit, reset) where remaining is the number of requests left,
               limit is the total allowed, and reset is the reset time as a unix timestamp.
    """
    rate = gh_client.get_rate_limit().core
    return rate.remaining, rate.limit, int(rate.reset.timestamp())


def get_wait_per_call(gh_client: Github, unique_users: int) -> float:
    """Calculate wait time per API call based on rate limit and number of users.

    Args:
        gh_client (Github): An authenticated PyGithub Github client.
        unique_users (int): Number of unique users to process.

    Returns:
        float: Seconds to wait before making the next API call.
    """
    remaining, _, reset = get_rate_limit_info(gh_client)
    now = int(time.time())
    seconds_to_reset = max(reset - now, 1)
    return (
        max(seconds_to_reset / max(remaining, 1), 1)
        if remaining < unique_users
        else 0.0
    )
