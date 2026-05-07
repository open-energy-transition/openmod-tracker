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


@pytest.fixture
def download_df():
    """Fixture to generate a DataFrame with PyPI package url and name."""
    return pd.DataFrame(
        {
            "id": ["pack_one", "pack_two", "pack_three"],
            "html_url": [
                "https://github.com/pack_one/pack_one",
                "https://github.com/pack_two/pack_two",
                "https://github.com/pack_three/pack_three",
            ],
            "pypi_package_url": [
                "https://pypi.org/project/pack_ONE",
                "https://pypi.org/project/pack_two",
                "https://pypi.org/project/PACK_three",
            ],
            "pypi_package_name": ["pack_ONE", "pack_two", "PACK_three"],
            "other_source": ["source_one", "source_two", "source_three"],
        }
    )


@pytest.fixture
def download_stats_df():
    """Fixture to generate a DataFrame with PyPI package download stats."""
    return pd.DataFrame(
        {
            "num_downloads": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
            "month": [
                "2026-05-01",
                "2026-04-01",
                "2026-03-01",
                "2026-05-01",
                "2026-04-01",
                "2026-03-01",
                "2026-05-01",
                "2026-04-01",
                "2026-03-01",
            ],
            "project": [
                "pack_one",
                "pack_one",
                "pack_one",
                "pack_two",
                "pack_two",
                "pack_two",
                "pack_four",
                "pack_four",
                "pack_four",
            ],
        }
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

    def test_enrich_with_monthly_downloads(
        self, download_df: pd.DataFrame, download_stats_df: pd.DataFrame
    ) -> None:
        """Test enrich_with_monthly_downloads function."""
        output_df = get_download_data.enrich_with_monthly_downloads(
            download_df, download_stats_df
        )
        expected_df = pd.DataFrame(
            {
                "id": ["pack_one", "pack_two", "pack_three"],
                "html_url": [
                    "https://github.com/pack_one/pack_one",
                    "https://github.com/pack_two/pack_two",
                    "https://github.com/pack_three/pack_three",
                ],
                "pypi_package_url": [
                    "https://pypi.org/project/pack_ONE",
                    "https://pypi.org/project/pack_two",
                    "https://pypi.org/project/PACK_three",
                ],
                "pypi_package_name": ["pack_ONE", "pack_two", "PACK_three"],
                "other_source": ["source_one", "source_two", "source_three"],
                "2026-05": ["1", "4", None],
                "2026-04": ["2", "5", None],
                "2026-03": ["3", "6", None],
            }
        )
        print(output_df)
        print(expected_df)
        pd.testing.assert_frame_equal(output_df, expected_df)
