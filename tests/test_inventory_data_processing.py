# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Inventory test suite."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from conftest import load_module_from_file

PROJ_DIR = Path().cwd()
INVENTORY_DIR = PROJ_DIR / "inventory"
TEST_URL_GITHUB = "https://github.com/pypsa/pypsa"
TEST_URL_GITLAB = "https://gitlab.com/mosaik/mosaik"

# Import modules
util = load_module_from_file(INVENTORY_DIR / "util.py", "util")
get_stats = load_module_from_file(INVENTORY_DIR / "get_stats.py", "get_stats")
get_scores = load_module_from_file(INVENTORY_DIR / "get_scores.py", "get_scores")


@pytest.fixture
def ecosystems_issue_api():
    """Skip test if ecosystems API is unavailable."""
    response = requests.get(util.ECOSYSTEMS_ISSUES_LOOKUP_API + TEST_URL, timeout=5)
    if response.status_code != 200:
        pytest.skip(
            f"Ecosystems issues API unavailable (status {response.status_code})"
        )


class TestInventoryUtil:
    """Test suite for inventory util functions."""

    def test_get_ecosystems_data(self, ecosystems_issue_api) -> None:
        """Test get_ecosystems_issues_data function."""
        result = util.get_ecosystems_issues_data(TEST_URL)
        assert isinstance(result, dict)
        assert result["full_name"].casefold() == "pypsa/pypsa"
        assert result["created_at"] == "2023-05-09T10:34:52.973Z"


class TestGetStats:
    """Test suite for get_stats functions."""

    MOCK_ECOSYSTEMS_RESPONSE = {
        "maintainers": [
            {
                "login": "user1",
                "count": 264,
                "url": "https://issues.ecosyste.ms/api/v1/hosts/GitHub/authors/user1",
            },
            {
                "login": "user2",
                "count": 254,
                "url": "https://issues.ecosyste.ms/api/v1/hosts/GitHub/authors/user2",
            },
            {
                "login": "user3",
                "count": 140,
                "url": "https://issues.ecosyste.ms/api/v1/hosts/GitHub/authors/user3",
            },
            {
                "login": "user4",
                "count": 36,
                "url": "https://issues.ecosyste.ms/api/v1/hosts/GitHub/authors/user4",
            },
            {
                "login": "user5",
                "count": 26,
                "url": "https://issues.ecosyste.ms/api/v1/hosts/GitHub/authors/user5",
            },
        ],
        "active_maintainers": [
            {
                "login": "user1",
                "count": 98,
                "url": "https://issues.ecosyste.ms/api/v1/hosts/GitHub/authors/user1",
            },
            {
                "login": "user2",
                "count": 31,
                "url": "https://issues.ecosyste.ms/api/v1/hosts/GitHub/authors/user2",
            },
        ],
    }

    @pytest.mark.parametrize(
        ("mock_response", "expected"),
        [
            (
                MOCK_ECOSYSTEMS_RESPONSE,
                2,
            ),  # has active_maintainers -> returns len(active_maintainers)
            (
                {
                    "maintainers": MOCK_ECOSYSTEMS_RESPONSE["maintainers"],
                    "active_maintainers": [],
                },
                0,
            ),  # no active -> fallback to maintainers
            (
                {"maintainers": [], "active_maintainers": []},
                -1,
            ),  # no maintainers at all
        ],
    )
    def test_get_number_of_maintainers(
        self, mock_response: dict, expected: int
    ) -> None:
        """Test _get_number_of_maintainers function with mocked API response."""
        with patch.object(
            get_stats.util, "get_ecosystems_issues_data", return_value=mock_response
        ):
            result = get_stats._get_number_of_maintainers(TEST_URL)
            assert isinstance(result, int)
            assert result == expected


class TestGetScores:
    """Test suite for get_scores.py functions."""

    @pytest.mark.parametrize(
        ("token_name", "token_value", "expected_result"),
        [
            ("GITHUB_AUTH_TOKEN", "test_token", True),
            ("GITHUB_TOKEN", "test_token", True),
            ("GH_AUTH_TOKEN", "test_token", True),
            ("GH_TOKEN", "test_token", True),
            ("GITLAB_AUTH_TOKEN", "test_token", False),
        ],
    )
    def test_github_url_with_any_github_token(
        self, token_name: str, token_value: str, expected_result: bool
    ) -> None:
        """Should return True for GitHub URLs when any GitHub token env var is set."""
        with patch.dict(os.environ, {token_name: token_value}, clear=True):
            assert get_scores.check_auth_token(TEST_URL_GITHUB) is expected_result

    @pytest.mark.parametrize(
        ("token_name", "token_value", "expected_result"),
        [("GH_TOKEN", "test_token", False), ("GITLAB_AUTH_TOKEN", "test_token", True)],
    )
    def test_gitlab_url_with_gitlab_token(
        self, token_name: str, token_value: str, expected_result: bool
    ) -> None:
        """Should return True for GitLab URLs when the GitLab token env var is set."""
        with patch.dict(os.environ, {token_name: token_value}, clear=True):
            assert get_scores.check_auth_token(TEST_URL_GITLAB) is expected_result
