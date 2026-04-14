# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Inventory test suite."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import load_module_from_file

PROJ_DIR = Path().cwd()
INVENTORY_DIR = PROJ_DIR / "inventory"
TEST_URL_GITHUB = "https://github.com/pypsa/pypsa"
TEST_URL_GITLAB = "https://gitlab.com/mosaik/mosaik"

# Import modules
util = load_module_from_file(INVENTORY_DIR / "util.py", "util")
get_scores = load_module_from_file(INVENTORY_DIR / "get_scores.py", "get_scores")


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
