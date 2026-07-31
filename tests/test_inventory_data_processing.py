# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Inventory test suite."""

import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
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
get_download_data = load_module_from_file(
    INVENTORY_DIR / "get_download_data.py", "get_download_data"
)

# Path to cache data (CSV file, not a module)
CACHE_DATA_PATH = INVENTORY_DIR / "manual_cache" / "package_urls_manual_search.csv"


@pytest.fixture
def ecosystems_issue_api():
    """Skip test if ecosystems API is unavailable."""
    response = requests.get(
        util.ECOSYSTEMS_ISSUES_LOOKUP_API + TEST_URL_GITHUB, timeout=5
    )
    if response.status_code != 200:
        pytest.skip(
            f"Ecosystems issues API unavailable (status {response.status_code})"
        )


@pytest.fixture
def download_df() -> pd.DataFrame:
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
def pypi_download_stats_df() -> pd.DataFrame:
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


@pytest.fixture
def conda_download_stats_df() -> pd.DataFrame:
    """Fixture to generate a DataFrame with Anaconda package download stats."""
    return pd.DataFrame(
        {
            "counts": ["1", "2", "3", "4", "6", "7", "8"],
            "time": [
                "2026-05-01",
                "2026-04-01",
                "2026-03-01",
                "2026-05-01",
                "2026-03-01",
                "2026-05-01",
                "2026-04-01",
            ],
            "pkg_name": [
                "pack_one",
                "pack_one",
                "pack_one",
                "pack_two",
                "pack_two",
                "pack_four",
                "pack_four",
            ],
        }
    )


@pytest.fixture
def conda_trend_df() -> pd.DataFrame:
    """Fixture mimicking raw conda download trend data across packages/months."""
    return pd.DataFrame(
        {
            "pkg_name": ["pypsa", "pypsa", "PyPSA", "other-pkg"],
            "time": ["2026-04", "2026-05", "2026-05", "2026-05"],
            "counts": [20, 7, 3, 999],
        }
    )


@pytest.fixture
def aggregated_conda_downloads_df(conda_trend_df: pd.DataFrame) -> pd.DataFrame:
    """Result of aggregating conda_trend_df for the "pypsa" package only."""
    return get_download_data._aggregate_conda_pkg_downloads(conda_trend_df, ["pypsa"])


@pytest.fixture
def partial_query_output_df(
    download_df: pd.DataFrame,
    pypi_download_stats_df: pd.DataFrame,
    conda_download_stats_df: pd.DataFrame,
) -> pd.DataFrame:
    """Enrich with a partial query scope: pack_one/pack_two only queried for 2026-05."""
    return get_download_data.enrich_with_monthly_downloads(
        download_df,
        pypi_download_stats_df,
        conda_download_stats_df,
        partial_query_pkgs={"pack_one", "pack_two"},
        partial_query_months={"2026-05"},
    )


@pytest.fixture
def overlap_merge_result_df() -> pd.DataFrame:
    """Merge result for new data with an overlapping month column that has gaps.

    Mirrors the real caching scenario: an existing tool wasn't queried for an
    older month this run (NaN placeholder, as enrich_with_monthly_downloads now
    produces), but the cache already holds a real value for that pkg-month.
    """
    new_data = pd.DataFrame(
        {
            "id": ["a", "b", "c"],
            "html_url": ["a-url", "b-url", "c-url"],
            "pypi_package_url": ["pypi-a-url", "pypi-b-url", "pypi-c-url"],
            "pypi_package_name": ["pkg-a", "pkg-b", "pkg-c"],
            "anaconda_package_url": ["conda-a-url", "conda-b-url", "conda-c-url"],
            "juliahub_package_url": [
                "juliahub-a-url",
                "juliahub-b-url",
                "juliahub-c-url",
            ],
            "other_source": ["other-a-url", "other-b-url", "other-c-url"],
            "2026-05": [100, 200, 300],
            "2026-04": [np.nan, 190, np.nan],
        }
    )
    cached_data = pd.DataFrame(
        {
            "id": ["a", "b", "c"],
            "html_url": ["a-url", "b-url", "c-url"],
            "pypi_package_url": ["pypi-a-url", "pypi-b-url", "pypi-c-url"],
            "pypi_package_name": ["pkg-a", "pkg-b", "pkg-c"],
            "anaconda_package_url": ["conda-a-url", "conda-b-url", "conda-c-url"],
            "juliahub_package_url": [
                "juliahub-a-url",
                "juliahub-b-url",
                "juliahub-c-url",
            ],
            "other_source": ["other-a-url", "other-b-url", "other-c-url"],
            "2026-04": [70, 999, 270],
            "2026-03": [80, 180, 280],
        }
    )
    return get_download_data.merge_with_cached_downloads(new_data, cached_data)


@pytest.fixture
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> pd.Timestamp:
    """Freeze pd.Timestamp.now() so month-based expectations don't drift with the real clock.

    get_expected_month_columns (and identify_missing_data, which calls it) derive
    their month range from pd.Timestamp.now(), so hardcoded expected months would
    otherwise silently go stale as real time passes.
    """
    fixed = pd.Timestamp("2026-06-15")
    monkeypatch.setattr(pd.Timestamp, "now", lambda tz=None: fixed)
    return fixed


@pytest.fixture
def sample_data() -> dict[str, pd.DataFrame]:
    """Create sample dataframes for testing."""
    return {
        "just_package_data_new_tool": pd.DataFrame(
            {
                "id": ["a", "b", "c", "d"],
                "html_url": ["a-url", "b-url", "c-url", "d-url"],
                "pypi_package_url": [
                    "pypi-a-url",
                    "pypi-b-url",
                    "pypi-c-url",
                    "pypi-d-url",
                ],
                "pypi_package_name": ["pkg-a", "pkg-b", "pkg-c", "pkg-d"],
                "anaconda_package_url": [
                    "conda-a-url",
                    "conda-b-url",
                    "conda-c-url",
                    "conda-d-url",
                ],
                "juliahub_package_url": [
                    "juliahub-a-url",
                    "juliahub-b-url",
                    "juliahub-c-url",
                    "juliahub-d-url",
                ],
                "other_source": [
                    "other-a-url",
                    "other-b-url",
                    "other-c-url",
                    "other-d-url",
                ],
            }
        ),
        "just_package_data": pd.DataFrame(
            {
                "id": ["a", "b", "c"],
                "html_url": ["a-url", "b-url", "c-url"],
                "pypi_package_url": ["pypi-a-url", "pypi-b-url", "pypi-c-url"],
                "pypi_package_name": ["pkg-a", "pkg-b", "pkg-c"],
                "anaconda_package_url": ["conda-a-url", "conda-b-url", "conda-c-url"],
                "juliahub_package_url": [
                    "juliahub-a-url",
                    "juliahub-b-url",
                    "juliahub-c-url",
                ],
                "other_source": ["other-a-url", "other-b-url", "other-c-url"],
            }
        ),
        "new_data": pd.DataFrame(
            {
                "id": ["a", "b", "c"],
                "html_url": ["a-url", "b-url", "c-url"],
                "pypi_package_url": ["pypi-a-url", "pypi-b-url", "pypi-c-url"],
                "pypi_package_name": ["pkg-a", "pkg-b", "pkg-c"],
                "anaconda_package_url": ["conda-a-url", "conda-b-url", "conda-c-url"],
                "juliahub_package_url": [
                    "juliahub-a-url",
                    "juliahub-b-url",
                    "juliahub-c-url",
                ],
                "other_source": ["other-a-url", "other-b-url", "other-c-url"],
                "2026-05": [100, 200, 300],
                "2026-04": [90, 190, 290],
            }
        ),
        "cached_data": pd.DataFrame(
            {
                "id": ["a", "b", "c"],
                "html_url": ["a-url", "b-url", "c-url"],
                "pypi_package_url": ["pypi-a-url", "pypi-b-url", "pypi-c-url"],
                "pypi_package_name": ["pkg-a", "pkg-b", "pkg-c"],
                "anaconda_package_url": ["conda-a-url", "conda-b-url", "conda-c-url"],
                "juliahub_package_url": [
                    "juliahub-a-url",
                    "juliahub-b-url",
                    "juliahub-c-url",
                ],
                "other_source": ["other-a-url", "other-b-url", "other-c-url"],
                "2026-03": [80, 180, 280],
                "2026-02": [70, 170, 270],
            }
        ),
    }


class TestInventoryUtil:
    """Test suite for inventory util functions."""

    def test_get_ecosystems_data(self, ecosystems_issue_api) -> None:
        """Test get_ecosystems_issues_data function."""
        result = util.get_ecosystems_issues_data(TEST_URL_GITHUB)
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
            result = get_stats._get_number_of_maintainers(TEST_URL_GITHUB)
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
        self,
        download_df: pd.DataFrame,
        pypi_download_stats_df: pd.DataFrame,
        conda_download_stats_df: pd.DataFrame,
    ) -> None:
        """Test enrich_with_monthly_downloads function."""
        output_df = get_download_data.enrich_with_monthly_downloads(
            download_df, pypi_download_stats_df, conda_download_stats_df
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
                "2026-05": [2.0, 8.0, None],
                "2026-04": [4.0, 5.0, None],
                "2026-03": [6.0, 12.0, None],
            }
        )
        pd.testing.assert_frame_equal(output_df, expected_df)

    @pytest.mark.parametrize(
        ("pkg_id", "month", "expected"),
        [
            # Queried month keeps its real value
            ("pack_one", "2026-05", 2.0),
            ("pack_two", "2026-05", 8.0),
            # Non-queried months are NaN, not zero-filled, for partially-queried packages
            ("pack_one", "2026-04", None),
            ("pack_one", "2026-03", None),
            ("pack_two", "2026-04", None),
            ("pack_two", "2026-03", None),
            # Package not in partial_query_pkgs is unaffected (still has no data)
            ("pack_three", "2026-05", None),
            ("pack_three", "2026-04", None),
            ("pack_three", "2026-03", None),
        ],
    )
    def test_enrich_with_monthly_downloads_partial_query(
        self,
        partial_query_output_df: pd.DataFrame,
        pkg_id: str,
        month: str,
        expected: float | None,
    ) -> None:
        """Packages only queried for a subset of months keep other months as NaN, not 0.

        Regression test: previously, unstack(fill_value=0) zero-filled every month
        column for every package, including packages (e.g. already-cached tools
        being backfilled with only the newest missing month) that were never
        queried for the older months. Those false zeros then overwrote real
        cached values in merge_with_cached_downloads.
        """
        value = partial_query_output_df.loc[
            partial_query_output_df["id"] == pkg_id, month
        ].iloc[0]
        if expected is None:
            assert pd.isna(value)
        else:
            assert value == expected

    @pytest.mark.parametrize(
        ("pkg_name", "time", "expected_counts"),
        [
            # Case-insensitive filter match, but grouping keeps original casing separate
            ("pypsa", "2026-04", 20),
            ("pypsa", "2026-05", 7),
            ("PyPSA", "2026-05", 3),
        ],
    )
    def test_aggregate_conda_pkg_downloads(
        self,
        aggregated_conda_downloads_df: pd.DataFrame,
        pkg_name: str,
        time: str,
        expected_counts: int,
    ) -> None:
        """Filtering and summing conda download counts, without any network call.

        This is the fast unit test for the filter/aggregate logic previously only
        exercised indirectly via test_get_conda_pkg_download_stats, which needed a
        real 12-month network fetch (~75s) to reach it.
        """
        row = aggregated_conda_downloads_df[
            (aggregated_conda_downloads_df["pkg_name"] == pkg_name)
            & (aggregated_conda_downloads_df["time"] == time)
        ]
        assert row["counts"].iloc[0] == expected_counts

    def test_aggregate_conda_pkg_downloads_excludes_other_packages(
        self, aggregated_conda_downloads_df: pd.DataFrame
    ) -> None:
        """Packages not in the requested list are filtered out."""
        assert "other-pkg" not in aggregated_conda_downloads_df["pkg_name"].values

    def test_get_conda_pkg_download_stats(self) -> None:
        """Smoke test that the network-backed pipeline wires filtering through correctly.

        Kept to a single month: the filter/aggregation logic itself is unit-tested
        without any network call in test_aggregate_conda_pkg_downloads above.
        """
        result = get_download_data.get_conda_pkg_download_stats(
            ["pypsa"], months_back=1
        )

        assert list(result.columns) == ["pkg_name", "time", "counts"]
        assert all(result["pkg_name"] == "pypsa")

    @pytest.mark.parametrize(
        (
            "id",
            "html_url",
            "pypi_url",
            "pypi_name",
            "anaconda_url",
            "julia_url",
            "other_url",
            "expected",
        ),
        [
            (
                "package",
                "https://github.com/package/package",
                "https://pypi.org/pkg",
                "package",
                None,
                None,
                None,
                True,
            ),
            (
                "package",
                "https://github.com/package/package.jl",
                None,
                None,
                None,
                "package",
                None,
                True,
            ),
            (
                "package",
                "https://github.com/package/package.jl",
                None,
                None,
                None,
                None,
                None,
                False,
            ),
            (
                "package",
                "https://github.com/package/package",
                None,
                None,
                None,
                None,
                None,
                False,
            ),
        ],
    )
    def test_should_skip_fetching_with_default_fields(
        self,
        id: str,
        html_url: str,
        pypi_url: str,
        pypi_name: str,
        anaconda_url: str,
        julia_url: str,
        other_url: str,
        expected: bool,
    ) -> None:
        """Test should_skip_fetching with default required fields."""
        row = pd.Series(
            {
                "id": id,
                "html_url": html_url,
                "pypi_package_url": pypi_url,
                "pypi_package_name": pypi_name,
                "anaconda_package_url": anaconda_url,
                "juliahub_package_url": julia_url,
                "other_source": other_url,
            }
        )
        result = get_download_data.should_skip_fetching(row)
        assert result == expected

    @pytest.mark.parametrize(
        (
            "url",
            "expected_pypi_url",
            "expected_conda_url",
            "expected_julia_url",
            "expected_other_url",
            "expected_package_name",
        ),
        [
            (
                TEST_URL_GITHUB,
                "https://pypi.org/project/pypsa",
                "https://anaconda.org/conda-forge/pypsa",
                None,
                None,
                "pypsa",
            ),
            (
                "https://gitlab.com/fame-framework/fame-core",
                None,
                None,
                None,
                "https://central.sonatype.com/artifact/de.dlr.gitlab.fame/core",
                None,
            ),
            (
                "https://github.com/YoungFaithful/CapacityExpansion.jl",
                None,
                None,
                "https://juliahub.com/ui/Packages/General/CapacityExpansion",
                None,
                None,
            ),
            (
                "https://github.com/leonardgoeke/AnyMOD.jl",
                None,
                None,
                "https://juliahub.com/ui/Packages/General/AnyMOD",
                None,
                None,
            ),
            (
                "https://github.com/rebase-energy/enflow",
                "https://pypi.org/project/enflow",
                None,
                None,
                None,
                "enflow",
            ),
            (
                "https://github.com/ait-energy/IESopt.jl",
                "https://pypi.org/project/iesopt",
                None,
                "https://juliahub.com/ui/Packages/General/IESopt",
                None,
                "iesopt",
            ),
            (
                "https://github.com/Sienna-Platform/PowerSimulationsDynamics.jl",
                None,
                None,
                "https://juliahub.com/ui/Packages/General/PowerSimulationsDynamics",
                None,
                None,
            ),
            (
                "https://github.com/RoseauTechnologies/Roseau_Load_Flow",
                "https://pypi.org/project/roseau-load-flow",
                None,
                None,
                None,
                "roseau-load-flow",
            ),
        ],
    )
    def test_get_tool_info(
        self,
        url: str,
        expected_pypi_url: str,
        expected_conda_url: str,
        expected_julia_url: str,
        expected_other_url: str,
        expected_package_name: str,
    ) -> None:
        """Test get_tool_info function."""
        package_info = get_download_data.get_tool_info(
            url, manual_cache=CACHE_DATA_PATH
        )
        assert package_info.pypi_package_url == expected_pypi_url
        assert package_info.anaconda_package_url == expected_conda_url
        assert package_info.juliahub_package_url == expected_julia_url
        assert package_info.other_source == expected_other_url
        assert package_info.pypi_package_name == expected_package_name

    def test_get_expected_month_columns(self, frozen_now: pd.Timestamp) -> None:
        """Test that get_expected_month_columns returns correct month columns."""
        expected_months = ["2026-05", "2026-04"]
        result = get_download_data.get_expected_month_columns(2)
        assert result == expected_months

    def test_merge_with_cached_downloads(
        self, sample_data: dict[str, pd.DataFrame]
    ) -> None:
        """Test merge_with_cached_downloads function."""
        result = get_download_data.merge_with_cached_downloads(
            sample_data["new_data"], sample_data["cached_data"]
        )
        expected = pd.DataFrame(
            {
                "id": ["a", "b", "c"],
                "html_url": ["a-url", "b-url", "c-url"],
                "pypi_package_url": ["pypi-a-url", "pypi-b-url", "pypi-c-url"],
                "pypi_package_name": ["pkg-a", "pkg-b", "pkg-c"],
                "anaconda_package_url": ["conda-a-url", "conda-b-url", "conda-c-url"],
                "juliahub_package_url": [
                    "juliahub-a-url",
                    "juliahub-b-url",
                    "juliahub-c-url",
                ],
                "other_source": ["other-a-url", "other-b-url", "other-c-url"],
                "2026-05": [100, 200, 300],
                "2026-04": [90, 190, 290],
                "2026-03": [80, 180, 280],
                "2026-02": [70, 170, 270],
            }
        )
        pd.testing.assert_frame_equal(expected, result)

    def test_merge_no_cached_with_downloads(
        self, sample_data: dict[str, pd.DataFrame]
    ) -> None:
        """Test merge_with_cached_downloads function."""
        result = get_download_data.merge_with_cached_downloads(
            sample_data["new_data"], None
        )
        expected = pd.DataFrame(
            {
                "id": ["a", "b", "c"],
                "html_url": ["a-url", "b-url", "c-url"],
                "pypi_package_url": ["pypi-a-url", "pypi-b-url", "pypi-c-url"],
                "pypi_package_name": ["pkg-a", "pkg-b", "pkg-c"],
                "anaconda_package_url": ["conda-a-url", "conda-b-url", "conda-c-url"],
                "juliahub_package_url": [
                    "juliahub-a-url",
                    "juliahub-b-url",
                    "juliahub-c-url",
                ],
                "other_source": ["other-a-url", "other-b-url", "other-c-url"],
                "2026-05": [100, 200, 300],
                "2026-04": [90, 190, 290],
            }
        )
        pd.testing.assert_frame_equal(expected, result)

    def test_merge_package_info_with_downloads(
        self, sample_data: dict[str, pd.DataFrame]
    ) -> None:
        """Test merge_with_cached_downloads function."""
        result = get_download_data.merge_with_cached_downloads(
            sample_data["just_package_data"], sample_data["new_data"]
        )
        expected = pd.DataFrame(
            {
                "id": ["a", "b", "c"],
                "html_url": ["a-url", "b-url", "c-url"],
                "pypi_package_url": ["pypi-a-url", "pypi-b-url", "pypi-c-url"],
                "pypi_package_name": ["pkg-a", "pkg-b", "pkg-c"],
                "anaconda_package_url": ["conda-a-url", "conda-b-url", "conda-c-url"],
                "juliahub_package_url": [
                    "juliahub-a-url",
                    "juliahub-b-url",
                    "juliahub-c-url",
                ],
                "other_source": ["other-a-url", "other-b-url", "other-c-url"],
                "2026-05": [100, 200, 300],
                "2026-04": [90, 190, 290],
            }
        )
        pd.testing.assert_frame_equal(expected, result)

    @pytest.mark.parametrize(
        ("pkg_id", "month", "expected"),
        [
            # Overlapping month with a gap (not queried this run): restored from cache
            ("a", "2026-04", 70),
            ("c", "2026-04", 270),
            # Overlapping month with a real freshly-queried value: new data wins over cache
            ("b", "2026-04", 190),
            # Cache-only month is carried over untouched
            ("a", "2026-03", 80),
            # New-only month is untouched
            ("a", "2026-05", 100),
        ],
    )
    def test_merge_with_cached_downloads_overlapping_months(
        self,
        overlap_merge_result_df: pd.DataFrame,
        pkg_id: str,
        month: str,
        expected: float,
    ) -> None:
        """Regression test: overlapping month columns must be combined cell-by-cell.

        Previously, a month column present in both new and cached data was left
        entirely as-is (cache was only consulted for columns missing outright),
        so a real cached value was permanently lost behind a placeholder from
        the new data.
        """
        value = overlap_merge_result_df.loc[
            overlap_merge_result_df["id"] == pkg_id, month
        ].iloc[0]
        assert value == expected

    def test_identify_missing_data(
        self, sample_data: dict[str, pd.DataFrame], frozen_now: pd.Timestamp
    ) -> None:
        """Test identify_missing_data function."""
        new_tools, existing_tools, missing_months = (
            get_download_data.identify_missing_data(
                sample_data["just_package_data_new_tool"],
                sample_data["cached_data"],
                months_back=4,
            )
        )
        assert new_tools == ["pkg-d"]
        assert sorted(existing_tools) == ["pkg-a", "pkg-b", "pkg-c"]
        assert missing_months == ["2026-05", "2026-04"]

    def test_identify_missing_data_no_new_tools_and_months(
        self, sample_data: dict[str, pd.DataFrame], frozen_now: pd.Timestamp
    ) -> None:
        """Test identify_missing_data function."""
        new_tools, existing_tools, missing_months = (
            get_download_data.identify_missing_data(
                sample_data["just_package_data"], sample_data["new_data"], months_back=2
            )
        )
        assert new_tools == list()
        assert sorted(existing_tools) == ["pkg-a", "pkg-b", "pkg-c"]
        assert missing_months == list()

    def test_identify_missing_data_no_cache_and_months(
        self, sample_data: dict[str, pd.DataFrame], frozen_now: pd.Timestamp
    ) -> None:
        """Test identify_missing_data function."""
        new_tools, existing_tools, missing_months = (
            get_download_data.identify_missing_data(
                sample_data["just_package_data"], None, months_back=2
            )
        )
        assert sorted(new_tools) == ["pkg-a", "pkg-b", "pkg-c"]
        assert sorted(existing_tools) == list()
        assert missing_months == ["2026-05", "2026-04"]
