"""GitHub Repository Interaction Collector.

This script fetches comprehensive repository interaction data using GitHub's GraphQL API with rate limiting, pagination, and error handling.
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import click
import pandas as pd
import requests
import util
from dotenv import load_dotenv
from github import Github
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

PAGINATION_CACHE = util.read_yaml("pagination_cache", exists=False)

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


@dataclass
class RateLimit:
    """GraphQL rate limit data."""

    limit: int
    cost: int
    remaining: int
    resetAt: str


class GitHubClient:
    """GitHub GraphQL/REST API client with rate limiting and pagination support."""

    def __init__(self, token: str | None):
        """GitHub API client.

        Methods are centred on querying GraphQL API client.
        However, for convenience, we also include an attribute with which the REST API can be queried.

        Args:
            token (str | None): GitHub API token.
        """
        self.base_url = "https://api.github.com/graphql"

        self.headers = {"Content-Type": "application/json"}
        if token is not None:
            self.headers["Authorization"] = f"Bearer {token}"

        self.rest_api = Github(token)
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def execute_query(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Execute a GraphQL query with error handling and rate limiting."""
        payload = {"query": query, "variables": variables}

        response = self.session.post(self.base_url, json=payload, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            return {}

        data = response.json()

        if "errors" in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

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


class GitHubRepositoryCollector:
    """Collects GitHub repository activity using GraphQL and REST APIs."""

    def __init__(self, token: str | None):
        """GitHub repository data collector.

        Args:
            token (str | None): GitHub API token.
        """
        self.client = GitHubClient(token)
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

    def _get_contributors(self, repo: str) -> list[dict]:
        """Get all users who are watching a repository.

        This requires a REST API query as the GraphQL doesn't have endpoints for high level stats.
        """
        repo_obj = self.client.rest_api.get_repo(repo)
        contributors = [
            {"username": contributor.login, "interaction": "contributor"}
            for contributor in repo_obj.get_contributors()
        ]
        remaining_calls = self.client.rest_api.get_rate_limit().core.remaining
        LOGGER.warning(f"Remaining REST API calls: {remaining_calls}.")
        return contributors

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

        # Fetch contributors (no timestamps)
        contributors = self._get_contributors(repo)
        results.extend(contributors)

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
    default="user_analysis/output/user_interactions.csv",
)
def cli(stats_file: Path, out_path: Path):
    """CLI entry point to collect all GitHub users who interact with the repositories listed in a stats file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        existing_users = pd.read_csv(out_path)
    else:
        existing_users = pd.DataFrame(columns=COLS, index=[])
        existing_users.to_csv(out_path, index=False)

    repos_df = pd.read_csv(stats_file, index_col=0)
    token = os.environ.get("GITHUB_TOKEN", None)
    collector = GitHubRepositoryCollector(token)
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

        df = collector.collect_repo_data(repo)
        if df.empty:
            LOGGER.warning(f"No users found for {repo}.")
            continue
        existing_users = (
            pd.concat([existing_users, df]).reindex(columns=COLS).drop_duplicates()
        )
        existing_users["number"] = existing_users["number"].astype("Int32")
        existing_users.to_csv(out_path, index=False)
        util.dump_yaml("pagination_cache", PAGINATION_CACHE)


if __name__ == "__main__":
    cli()
