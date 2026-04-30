# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Inventory test suite."""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import requests
from conftest import load_module_from_file

PROJ_DIR = Path().cwd()
INVENTORY_DIR = PROJ_DIR / "inventory"
TEST_URL = "https://github.com/pypsa/pypsa"


# Import modules
util = load_module_from_file(INVENTORY_DIR / "util.py", "util")
get_stats = load_module_from_file(INVENTORY_DIR / "get_stats.py", "get_stats")
get_download_data = load_module_from_file(
    INVENTORY_DIR / "get_download_data.py", "get_download_data"
)


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


class TestGetDownloadData:
    """Test suite for get_download_data functions."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            # Valid cases
            ("valid_package", True),
            ("https://pypi.org/project/package", True),
            # Invalid cases
            ("", False),
            ("   ", False),
            ("\t\n  ", False),
            (" ", False),
            (None, False),
            (np.nan, False),
            (pd.NA, False),
        ],
    )
    def test_is_populated(self, value, expected):
        """Test _is_populated with various value types and edge cases."""
        row = pd.Series({"col": value})
        assert get_download_data._is_populated(row, "col") is expected
