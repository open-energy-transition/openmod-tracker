# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Authenticated GitHub API client using PyGithub."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import requests
import util
from dotenv import load_dotenv
from github import Github
from github.GithubException import GithubException, RateLimitExceededException

load_dotenv()
LOGGER = logging.getLogger(__name__)

PAGINATION_CACHE = util.read_yaml("pagination_cache_gh", exists=False)


@dataclass
class RateLimit:
    """GraphQL rate limit data."""

    limit: int
    cost: int
    remaining: int
    resetAt: str


class GitHubClientGH:
    """GitHub GraphQL/REST API client with rate limiting and pagination support."""

    def __init__(self, token: str | None = None):
        """GitHub API client.

        Methods are centred on querying GraphQL API client.
        However, for convenience, we also include an attribute with which the REST API can be queried.

        Args:
            token (str | None, optional):
                GitHub API token.
                If not provided, will attempt to read from environment variable ``GITHUB_TOKEN``.
                Defaults to None.
        """
        self.base_url = "https://api.github.com/graphql"

        self.headers = {"Content-Type": "application/json"}
        token = token or os.environ.get("GITHUB_TOKEN")
        if token:
            LOGGER.info("Using provided GitHub token for authentication")
            # Private-token is acceptable, also 'Authorization: Bearer <token>' works for PATs
            self.headers["Authorization"] = f"Bearer {token}"
        else:
            LOGGER.warning("No GitHub token provided; proceeding unauthenticated")

        self.rest_api = Github(token)
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def execute_query(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Execute a GraphQL query with error handling and rate limiting."""
        payload = {"query": query, "variables": variables}

        response = self.session.post(self.base_url, json=payload, timeout=30)
        try:
            response.raise_for_status()
        except requests.RequestException:
            return {}

        data = response.json()

        if "errors" in data:
            LOGGER.error(f"GraphQL errors: {data['errors']}")
            return {}

        # Handle rate limiting
        if "data" in data and "rateLimit" in data["data"]:
            rate_limit = RateLimit(**data["data"]["rateLimit"])
            LOGGER.warning(
                f"Rate limit - Cost: {rate_limit.cost}, Remaining: {rate_limit.remaining}/{rate_limit.limit}"
            )

            # If we're running low on rate limit, wait
            if rate_limit.remaining < 100:
                reset_time = datetime.fromisoformat(
                    rate_limit.resetAt.replace("Z", "+00:00")
                )
                # Add 20 second buffer
                wait_time = (reset_time - datetime.now(UTC)).total_seconds() + 20
                LOGGER.warning(f"Rate limit low. Waiting {wait_time:.0f} seconds...")
                time.sleep(wait_time)

        return data["data"]

    def get_rate_limit_info(self) -> tuple[int, int, int]:
        """Get the current GitHub REST API rate limit status for the core resource.

        Returns:
            tuple: (remaining, limit, reset) where remaining is the number of requests left,
                limit is the total allowed, and reset is the reset time as a unix timestamp.
        """
        rate = self.rest_api.get_rate_limit().rate
        return rate.remaining, rate.limit, int(rate.reset.timestamp())


class GitHubRepositoryCollectorGH:
    """Collects GitHub repository activity using GraphQL and REST APIs."""

    def __init__(self, token: str | None = None):
        """GitHub repository data collector.

        Args:
            token (str | None, optional): GitHub API token. Defaults to None.
        """
        token = token or os.environ.get("GITHUB_TOKEN")
        self.client = GitHubClientGH(token)
        self.queries = self._load_queries()

    def _load_queries(self) -> dict[str, str]:
        """Load GraphQL queries."""
        return {
            "issues": """
                query RepositoryIssues($owner: String!, $name: String!, $cursor: String) {
                  repository(owner: $owner, name: $name) {
                    name
                    createdAt
                    issues(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
                      totalCount
                      pageInfo {
                        hasNextPage
                        endCursor
                      }
                      nodes {
                        createdAt
                        closedAt
                        number
                        author {
                          login
                        }
                        comments(first: 25) {
                          totalCount
                          nodes {
                            createdAt
                            author {
                              login
                            }
                          }
                        }
                        reactions(first: 10) {
                          totalCount
                          nodes {
                            createdAt
                            user {
                              login
                            }
                          }
                        }
                      }
                    }
                  }
                  rateLimit {
                    limit
                    cost
                    remaining
                    resetAt
                  }
                }
            """,
            "pullRequests": """
                query RepositoryPullRequests($owner: String!, $name: String!, $cursor: String) {
                  repository(owner: $owner, name: $name) {
                    pullRequests(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
                      totalCount
                      pageInfo {
                        hasNextPage
                        endCursor
                      }
                      nodes {
                        createdAt
                        closedAt
                        mergedAt
                        number
                        author {
                          login
                        }
                        comments(first: 25) {
                          totalCount
                          nodes {
                            createdAt
                            author {
                              login
                            }
                          }
                        }
                        reviews(first: 5) {
                          totalCount
                          nodes {
                            createdAt
                            author {
                              login
                            }
                          }
                        }
                        reactions(first: 10) {
                          totalCount
                          nodes {
                            createdAt
                            user {
                              login
                            }
                          }
                        }
                      }
                    }
                  }
                  rateLimit {
                    limit
                    cost
                    remaining
                    resetAt
                  }
                }
            """,
            "stargazers": """
                query RepositoryStargazers($owner: String!, $name: String!, $cursor: String) {
                  repository(owner: $owner, name: $name) {
                    stargazers(first: 100, after: $cursor, orderBy: {field: STARRED_AT, direction: ASC}) {
                      totalCount
                      pageInfo {
                        hasNextPage
                        endCursor
                      }
                      edges {
                        starredAt
                        node {
                          login
                        }
                      }
                    }
                  }
                  rateLimit {
                    limit
                    cost
                    remaining
                    resetAt
                  }
                }
            """,
            "forks": """
                query RepositoryForks($owner: String!, $name: String!, $cursor: String) {
                  repository(owner: $owner, name: $name) {
                    forks(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
                      totalCount
                      pageInfo {
                        hasNextPage
                        endCursor
                      }
                      nodes {
                        createdAt
                        owner {
                          login
                        }
                      }
                    }
                  }
                  rateLimit {
                    limit
                    cost
                    remaining
                    resetAt
                  }
                }
            """,
            "commits": """
                query RepositoryCommits($owner: String!, $name: String!, $cursor: String) {
                  repository(owner: $owner, name: $name) {
                    defaultBranchRef {
                      target {
                        ... on Commit {
                          history(first: 100, after: $cursor) {
                            totalCount
                            pageInfo {
                              hasNextPage
                              endCursor
                            }
                            nodes {
                              committedDate
                              author {
                                user {
                                  login
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                  rateLimit {
                    limit
                    cost
                    remaining
                    resetAt
                  }
                }
            """,
        }

    def _parse_author(self, author_data: dict | None) -> str | None:
        """Parse GraphQL dict response author entry to get username (if available)."""
        if author_data is None:
            return None
        else:
            return author_data.get("login", None)

    def _paginate_query(self, query_name: str, repo: str) -> list[dict]:
        """Execute a query with pagination support."""
        all_data = []
        owner, name = repo.strip("/").split("/")
        cache_key = f"{owner}.{name}.{query_name}"
        cursor = PAGINATION_CACHE.get(cache_key, None)
        page = 1

        while True:
            LOGGER.warning(f"Fetching {query_name} - Page: {page} - Cursor: {cursor}")

            variables = {"owner": owner, "name": name, "cursor": cursor}

            data = self.client.execute_query(self.queries[query_name], variables)
            if not data:
                break
            # Extract the relevant data based on query type
            if query_name == "commits":
                # Special handling for commits nested structure
                default_branch = data["repository"].get("defaultBranchRef")
                if default_branch is None:
                    LOGGER.warning(f"No default branch found for {repo}")
                    break
                items = default_branch["target"]["history"]
            else:
                items = data["repository"][query_name]

            if query_name == "stargazers":
                all_data.extend(items["edges"])
            else:
                all_data.extend(items["nodes"])

            if not items["pageInfo"]["hasNextPage"]:
                break
            cursor = items["pageInfo"]["endCursor"]
            PAGINATION_CACHE[cache_key] = cursor
            page += 1
        if page > 1:
            util.dump_yaml("pagination_cache_gh", PAGINATION_CACHE)
        LOGGER.warning(f"Fetched {len(all_data)} {query_name} items")
        return all_data

    def _parse_issue_data(self, issue_data: dict) -> list[dict]:
        """Parse issues to get created/closed timestamps and the usernames associated with the author, comments, and reactions."""
        results = []
        data_type = "issue"

        author = {
            "interaction": data_type,
            "subtype": "author",
            "number": issue_data["number"],
            "username": self._parse_author(issue_data.get("author")),
            "created": issue_data["createdAt"],
            "closed": issue_data.get("closedAt"),
        }
        results.append(author)

        for comment in issue_data.get("comments", {}).get("nodes", []):
            results.append(
                {
                    "interaction": data_type,
                    "subtype": "comment",
                    "number": issue_data["number"],
                    "username": self._parse_author(comment.get("author")),
                    "created": comment["createdAt"],
                }
            )

        for reaction in issue_data.get("reactions", {}).get("nodes", []):
            results.append(
                {
                    "interaction": data_type,
                    "subtype": "reaction",
                    "number": issue_data["number"],
                    "username": self._parse_author(reaction.get("author")),
                    "created": reaction["createdAt"],
                }
            )
        return results

    def _parse_pr_data(self, pr_data: dict) -> list[dict]:
        """Parse PRs to get created/closed/merged timestamps and the usernames associated with the author, comments, reviews, and reactions."""
        results = []
        data_type = "pr"
        author = {
            "interaction": data_type,
            "subtype": "author",
            "number": pr_data["number"],
            "username": self._parse_author(pr_data.get("author")),
            "created": pr_data["createdAt"],
            "closed": pr_data.get("closedAt") if not pr_data.get("mergedAt") else None,
            "merged": pr_data.get("mergedAt"),
        }
        results.append(author)

        for comment in pr_data.get("comments", {}).get("nodes", []):
            results.append(
                {
                    "interaction": data_type,
                    "subtype": "comment",
                    "number": pr_data["number"],
                    "username": self._parse_author(comment.get("author")),
                    "created": comment["createdAt"],
                }
            )

        for reaction in pr_data.get("reactions", {}).get("nodes", []):
            results.append(
                {
                    "interaction": data_type,
                    "subtype": "reaction",
                    "number": pr_data["number"],
                    "username": self._parse_author(reaction.get("author")),
                    "created": reaction["createdAt"],
                }
            )

        for reviewer in pr_data.get("reviews", {}).get("nodes", []):
            results.append(
                {
                    "interaction": data_type,
                    "subtype": "review",
                    "number": pr_data["number"],
                    "username": self._parse_author(reviewer.get("author")),
                    "created": reviewer["createdAt"],
                }
            )
        return results

    def _parse_star_data(self, star_data: dict) -> dict:
        return {
            "interaction": "stargazer",
            "username": self._parse_author(star_data.get("node")),
            "created": star_data["starredAt"],
        }

    def _parse_fork_data(self, fork_data: dict) -> dict:
        return {
            "interaction": "fork",
            "username": self._parse_author(fork_data.get("owner")),
            "created": fork_data["createdAt"],
        }

    def _parse_commit_data(
        self, commit_data: dict, is_default_branch: bool = True
    ) -> dict:
        """Parse commit data to extract author username and commit date.

        Args:
            commit_data: GraphQL commit node data
            is_default_branch: Whether this commit is from the default branch
        """
        author_info = commit_data.get("author", {})
        # Try to get GitHub username first, fall back to git author name
        username = None
        if author_info.get("user"):
            username = author_info["user"].get("login")
        if username is None:
            # Fall back to git author name or email
            username = author_info.get("name") or author_info.get("email")

        return {
            "interaction": "commit",
            "subtype": "default_branch" if is_default_branch else "other_branch",
            "username": username,
            "created": commit_data["committedDate"],
        }

    def collect_repo_data(self, repo: str) -> pd.DataFrame:
        """Analyze a GitHub repository and return comprehensive activity data."""
        LOGGER.warning(f"Starting analysis of {repo}")

        results = []

        # Fetch issues
        issues_data = self._paginate_query("issues", repo)
        for issue_data in issues_data:
            results.extend(self._parse_issue_data(issue_data))

        # Fetch pull requests
        prs_data = self._paginate_query("pullRequests", repo)
        for pr_data in prs_data:
            results.extend(self._parse_pr_data(pr_data))

        # Fetch stargazers
        stars_data = self._paginate_query("stargazers", repo)
        for star_data in stars_data:
            results.append(self._parse_star_data(star_data))

        # Fetch forks
        forks_data = self._paginate_query("forks", repo)
        for fork_data in forks_data:
            results.append(self._parse_fork_data(fork_data))

        # Fetch commits (optional - can be expensive for large repos)
        # Uncomment the lines below to collect commit statistics
        # Note: This query only fetches commits from the default branch
        commits_data = self._paginate_query("commits", repo)
        for commit_data in commits_data:
            results.append(self._parse_commit_data(commit_data, is_default_branch=True))

        LOGGER.warning(f"Analysis complete. Found {len(results)} interactions")
        results_df = pd.DataFrame(results).assign(repo=repo)

        # Simplify datetime strings to reduce size on disk
        for ts_col in ["created", "closed", "merged"]:
            if ts_col not in results_df:
                continue
            results_df[ts_col] = pd.to_datetime(results_df[ts_col]).dt.tz_localize(None)
        if "number" in results_df:
            results_df["number"] = results_df["number"].astype("Int16")
        return results_df


def get_user_details_gh(
    username: str, repos: set[str], gh_client: GitHubClientGH, wait: float = 0.0
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
        user = gh_client.rest_api.get_user(username)
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
                gh_client.rest_api.get_repo(f"{username}/{username}")
                .get_readme()
                .decoded_content.decode()
            )
        except GithubException:
            readme = ""
        user_data["readme"] = readme.strip() if readme is not None else ""
        # Get user's organizations
        orgs = list(user.get_orgs())
        user_data["orgs"] = ",".join(org.login for org in orgs)
        orgs_df = pd.DataFrame(
            {
                "description": [
                    desc.strip() if (desc := org.description) is not None else ""
                    for org in orgs
                ]
            },
            index=pd.Index([org.login for org in orgs], name="orgname"),
        )
        user_df = pd.DataFrame(user_data, index=pd.Index([username], name="username"))
        return user_df, orgs_df
    except RateLimitExceededException:
        LOGGER.warning("Rate limit exceeded while fetching user details.")
        if wait == 0:
            return get_user_details_gh(username, repos, gh_client, 120)
        else:
            return pd.DataFrame(), pd.DataFrame()
    except GithubException as e:
        if e.status == 429 and wait == 0:
            LOGGER.warning("Fair use limit exceeded while fetching user details.")
            return get_user_details_gh(username, repos, gh_client, 120)
        else:
            LOGGER.warning(f"Failed to fetch user details for {username}: {e}")
            return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        LOGGER.warning(f"Failed to fetch user details for {username}: {e}")
        return pd.DataFrame(), pd.DataFrame()
