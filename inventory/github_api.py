"""Authenticated GitHub API client using PyGithub."""

import logging
import os

from dotenv import load_dotenv
from github import Github

load_dotenv()
LOGGER = logging.getLogger(__name__)
GH_API_KEY: str | None = os.environ.get("GITHUB_TOKEN", None)


def get_github_client() -> Github:
    """Get an authenticated PyGithub Github client using the GITHUB_TOKEN environment variable.

    Returns:
        Github: An authenticated PyGithub Github client (or unauthenticated if no token is set).
    """
    if GH_API_KEY:
        return Github(GH_API_KEY)
    else:
        return Github()


def get_rate_limit_info(g: Github | None = None):
    """Get the current GitHub API rate limit status for the core resource.

    Args:
        g (Github, optional): An authenticated PyGithub Github client. If None, a new client is created.

    Returns:
        tuple: (remaining, limit, reset) where remaining is the number of requests left,
               limit is the total allowed, and reset is the reset time as a unix timestamp.
    """
    if g is None:
        g = get_github_client()
    rate = g.get_rate_limit().core
    return rate.remaining, rate.limit, int(rate.reset.timestamp())
