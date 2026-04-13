# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Inventory test suite."""

from pathlib import Path

import pytest
import requests
from conftest import load_module_from_file

PROJ_DIR = Path().cwd()
INVENTORY_DIR = PROJ_DIR / "inventory"
TEST_URL = "https://github.com/pypsa/pypsa"


# Import modules
util = load_module_from_file(INVENTORY_DIR / "util.py", "util")
get_stats = load_module_from_file(INVENTORY_DIR / "get_stats.py", "get_stats")


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

    def test_get_number_of_maintainers(self, ecosystems_issue_api) -> None:
        """Test _get_number_of_maintainers function."""
        result = get_stats._get_number_of_maintainers(TEST_URL)
        assert isinstance(result, int)
        assert result == 5
