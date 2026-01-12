# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Lightweight GitLab API client using requests.

Supports GitLab.com by default and self-hosted GitLab instances via GITLAB_BASE_URL.
Authentication via a personal access token provided in GITLAB_TOKEN.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests
import util
from dotenv import load_dotenv

load_dotenv()
LOGGER = logging.getLogger(__name__)

# Default base API URL for GitLab.com REST v4
DEFAULT_BASE_URL = "https://gitlab.com/api/v4"

PAGINATION_CACHE = util.read_yaml("pagination_cache_gl", exists=False)


@dataclass
class GitLabRateLimit:
    """Represents simplistic rate handling window.

    GitLab does not return a single global core limit like GitHub.
    We conservatively sleep between paginated requests when a 429 is hit.
    """

    sleep_seconds: float = 1.0


class GitLabClientGL:
    """Minimal GitLab REST API client with pagination and basic retries."""

    def __init__(self, token: str | None = None, base_url: str | None = None):
        """Create a GitLab client.

        Args:
            token (str | None, optional):
                Personal access token (PAT) for authentication.
                If not provided, will attempt to read from environment variable ``GITLAB_TOKEN``.
                Defaults to None.
            base_url (str | None, optional): Override for self-hosted GitLab API base (e.g. https://gitlab.example.com/api/v4).
                If omitted, uses environment variable ``GITLAB_BASE_URL`` or the public gitlab.com API.
                Defaults to None.
        """
        self.base_url = (
            base_url or os.environ.get("GITLAB_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.session = requests.Session()
        headers = {"Accept": "application/json"}
        token = token or os.environ.get("GITLAB_TOKEN")
        if token:
            LOGGER.info("Using provided GitLab token for authentication")
            # Private-token is acceptable, also 'Authorization: Bearer <token>' works for PATs
            headers["PRIVATE-TOKEN"] = token
        else:
            LOGGER.warning("No GitLab token provided; proceeding unauthenticated")
        self.session.headers.update(headers)
        self.rate = GitLabRateLimit()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            resp = self.session.request(method, url, timeout=120, **kwargs)
            resp.raise_for_status()
        except Exception as e:
            LOGGER.error(f"GitLab API request error: {e}")
            pass
        return resp

    def _paginate(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        """Paginate a GitLab list endpoint, yielding items."""
        page = PAGINATION_CACHE.get(path, 0)
        params = params.copy() if params else {}
        params.setdefault("per_page", 100)
        while True:
            page += 1
            params["page"] = page
            resp = self._request("GET", path, params=params)
            items = resp.json()
            if not isinstance(items, list) or not items:
                break
            yield from items
            # Stop when fewer than per_page returned
            if len(items) < params["per_page"]:
                break
        if page > 1:
            PAGINATION_CACHE[path] = page
            util.dump_yaml("pagination_cache_gl", PAGINATION_CACHE)

    @staticmethod
    def encode_project_path(path: str) -> str:
        """URL-encode a project path (namespace/project) for use as :id in /projects/:id endpoints."""
        # GitLab expects full path URL-encoded, e.g. group/subgroup%2Fproject
        return quote(path, safe="")

    # --- Project-level endpoints ---

    def get_project(self, full_path: str) -> dict[str, Any]:
        """Retrieve a project record by its full path (namespace/project)."""
        return self._request(
            "GET", f"projects/{self.encode_project_path(full_path)}"
        ).json()

    def list_issues(self, full_path: str) -> Iterable[dict[str, Any]]:
        """Iterate issues for a project (ascending by creation time)."""
        project = self.encode_project_path(full_path)
        return self._paginate(
            f"projects/{project}/issues",
            params={"order_by": "created_at", "sort": "asc"},
        )

    def list_issue_notes(
        self, full_path: str, issue_iid: int
    ) -> Iterable[dict[str, Any]]:
        """Iterate issue notes (comments) for an issue IID within a project."""
        project = self.encode_project_path(full_path)
        return self._paginate(f"projects/{project}/issues/{issue_iid}/notes")

    def list_merge_requests(self, full_path: str) -> Iterable[dict[str, Any]]:
        """Iterate merge requests for a project (ascending by creation time)."""
        project = self.encode_project_path(full_path)
        return self._paginate(
            f"projects/{project}/merge_requests",
            params={"order_by": "created_at", "sort": "asc"},
        )

    def list_mr_notes(self, full_path: str, mr_iid: int) -> Iterable[dict[str, Any]]:
        """Iterate merge request notes (comments) for an MR IID within a project."""
        project = self.encode_project_path(full_path)
        return self._paginate(f"projects/{project}/merge_requests/{mr_iid}/notes")

    def list_forks(self, full_path: str) -> Iterable[dict[str, Any]]:
        """Iterate forks for a project."""
        project = self.encode_project_path(full_path)
        return self._paginate(f"projects/{project}/forks")

    def list_commits(self, full_path: str) -> Iterable[dict[str, Any]]:
        """Iterate commits for a project (default branch first by GitLab ordering)."""
        project = self.encode_project_path(full_path)
        return self._paginate(f"projects/{project}/repository/commits")

    def list_stargazers(self, full_path: str) -> Iterable[dict[str, Any]]:
        """Get all project starrers."""
        project = self.encode_project_path(full_path)
        return self._paginate(f"projects/{project}/starrers")

    # NOTE: GitLab does not expose stargazers list via public API; skipping

    # --- User endpoints ---

    def find_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Find a user by username (returns the first matching user or None)."""
        resp = self._request("GET", "users", params={"username": username}).json()
        if isinstance(resp, list) and resp:
            return self.get_user(resp[0]["id"])
        return None

    def get_user(self, user_id: int) -> dict[str, Any]:
        """Get a user by numeric ID."""
        return self._request("GET", f"users/{user_id}").json()


class GitLabRepositoryCollectorGL:
    """Collects GitLab repository activity using REST API endpoints."""

    def __init__(self, token: str | None = None, base_url: str | None = None):
        """Initialize collector with underlying GitLab client."""
        self.client = GitLabClientGL(token=token, base_url=base_url)

    def _parse_username(self, author: dict[str, Any] | None) -> str | None:
        if not author:
            return None
        # Prefer username, fallback to name
        return author.get("username") or author.get("name")

    def collect_repo_data(self, repo_path: str) -> pd.DataFrame:
        """Analyze a GitLab project and return activity data.

        Args:
            repo_path: Full path of project (e.g. group/subgroup/project)
        """
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
        results: list[dict[str, Any]] = []
        try:
            self.client.get_project(repo_path)  # Validate project exists
        except requests.HTTPError as e:
            LOGGER.error(f"Failed to access GitLab project {repo_path}: {e}")
            return pd.DataFrame(columns=COLS)
        # Issues + comments
        for issue in self.client.list_issues(repo_path):
            iid = issue.get("iid")
            if iid is None:
                continue
            results.append(
                {
                    "interaction": "issue",
                    "subtype": "author",
                    "number": iid,
                    "username": self._parse_username(issue.get("author")),
                    "created": issue.get("created_at"),
                    "closed": issue.get("closed_at"),
                }
            )
            for note in self.client.list_issue_notes(repo_path, iid):
                results.append(
                    {
                        "interaction": "issue",
                        "subtype": "comment",
                        "number": iid,
                        "username": self._parse_username(note.get("author")),
                        "created": note.get("created_at"),
                    }
                )

        # Merge requests + comments
        for mr in self.client.list_merge_requests(repo_path):
            iid = mr.get("iid")
            if iid is None:
                continue
            results.append(
                {
                    "interaction": "pr",  # keep column naming consistent with GitHub (treated as PRs)
                    "subtype": "author",
                    "number": iid,
                    "username": self._parse_username(mr.get("author")),
                    "created": mr.get("created_at"),
                    "closed": mr.get("closed_at") if not mr.get("merged_at") else None,
                    "merged": mr.get("merged_at"),
                }
            )
            for note in self.client.list_mr_notes(repo_path, iid):
                results.append(
                    {
                        "interaction": "pr",
                        "subtype": "comment",
                        "number": iid,
                        "username": self._parse_username(note.get("author")),
                        "created": note.get("created_at"),
                    }
                )

        # Forks
        for fork in self.client.list_forks(repo_path):
            # fork project payload contains namespace info; best effort username
            ns = fork.get("namespace") or {}
            username = ns.get("full_path") or fork.get("path_with_namespace")
            results.append(
                {
                    "interaction": "fork",
                    "username": username,
                    "created": fork.get("created_at"),
                }
            )

        # Stargazers
        for starrer in self.client.list_stargazers(repo_path):
            # starrer payload contains user info; best effort username
            user = starrer.get("user") or {}
            username = user.get("username")
            results.append(
                {
                    "interaction": "stargazer",
                    "username": user.get("username"),
                    "created": starrer.get("starred_since"),
                }
            )
        # Commits
        for commit in self.client.list_commits(repo_path):
            username = commit.get("author_email") or commit.get("author_name")
            results.append(
                {
                    "interaction": "commit",
                    "subtype": "default_branch",  # GitLab endpoint returns default ordering; we don't distinguish here
                    "username": username,
                    "created": commit.get("created_at"),
                }
            )
        if not results:
            LOGGER.info(f"No interactions found for {repo_path}")
            return pd.DataFrame(columns=COLS)

        df = pd.DataFrame(results).assign(repo=repo_path)
        # Harmonize columns
        for col in ("number", "closed", "merged", "subtype"):
            if col not in df:
                df[col] = pd.Series(dtype="float") if col == "number" else None
        # Parse timestamps (keep naive)
        for ts_col in ["created", "closed", "merged"]:
            if ts_col in df:
                col_no_sub_seconds = df[ts_col].str.split(".", expand=True)[0]
                df[ts_col] = pd.to_datetime(
                    col_no_sub_seconds, utc=True
                ).dt.tz_localize(None)
        if "number" in df:
            df["number"] = df["number"].astype("Int16")
        return df[COLS]


def _domain_from_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1]


def get_user_details_gl(
    username: str, repos: set[str], client: GitLabClientGL
) -> pd.DataFrame:
    """Get user details for a GitLab user by username.

    Returns user_df (index=username).
    Missing fields compared to GitHub are returned empty.
    """
    user = client.find_user_by_username(username)
    if not user:
        LOGGER.warning(f"Could not find GitLab user for username: {username}")
        return pd.DataFrame()

    # Basic profile fields
    company = user.get("organization")
    blog = user.get("website_url")
    location = user.get("location")
    bio = user.get("bio")
    public_email = user.get("public_email")
    twitter = user.get("twitter")
    job_title = user.get("job_title") or ""
    work_info = user.get("work_information") or ""
    if job_title or work_info:
        readme = " - ".join([job_title, work_info])
    else:
        readme = ""

    user_data = {
        "company": company,
        "blog": blog,
        "location": location,
        "email_domain": _domain_from_email(public_email),
        "bio": bio,
        "twitter_username": twitter,
        "repos": ",".join(sorted(repos)),
        "readme": readme,
    }

    user_df = pd.DataFrame(user_data, index=pd.Index([username], name="username"))
    return user_df
