# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Test suite for collecting anonymous GitHub star history.

Stargazer listings are restricted to repository admins/collaborators, so stars are collected from the
star history endpoint, which reports per-day counts with no user identity.
"""

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

USER_ANALYSIS_DIR = Path(__file__).parent.parent / "user_analysis"
sys.path.insert(0, str(USER_ANALYSIS_DIR))

import get_repo_interactions  # noqa: E402
import github_api  # noqa: E402


def week_bucket(start: date, days: list[int]) -> dict:
    """Build one weekly star history bucket, as returned by the API."""
    return {
        "week": int(
            datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp()
        ),
        "total": sum(days),
        "days": days,
    }


@pytest.fixture
def collector(monkeypatch):
    """A collector whose REST calls are served from a stubbed, paginated star history."""
    monkeypatch.setattr(github_api, "STAR_HISTORY_PER_PAGE", 2)
    collector = github_api.GitHubRepositoryCollectorGH.__new__(
        github_api.GitHubRepositoryCollectorGH
    )
    collector.queries = {}
    return collector


@pytest.fixture
def stub_history(collector, monkeypatch):
    """Serve a fixed list of weekly buckets (newest first) through paginated REST responses."""

    def _stub(weeks: list[dict]):
        calls = []

        def execute_rest_query(path, params=None):
            calls.append(params["page"])
            start = (params["page"] - 1) * params["per_page"]
            return weeks[start : start + params["per_page"]]

        client = type(
            "Client", (), {"execute_rest_query": staticmethod(execute_rest_query)}
        )()
        monkeypatch.setattr(collector, "client", client, raising=False)
        return calls

    return _stub


class TestStarHistoryDays:
    """Flattening weekly star history buckets into per-day counts."""

    def test_flattens_weeks_to_days(self):
        """Each day in a week bucket becomes its own dated count."""
        weeks = [week_bucket(date(2026, 5, 3), [0, 2, 0, 0, 1, 0, 0])]
        assert github_api.GitHubRepositoryCollectorGH._star_history_days(weeks) == {
            date(2026, 5, 4): 2,
            date(2026, 5, 7): 1,
        }

    def test_drops_days_without_stars(self):
        """Days nobody starred on are not carried through."""
        weeks = [week_bucket(date(2026, 5, 3), [0] * 7)]
        assert github_api.GitHubRepositoryCollectorGH._star_history_days(weeks) == {}


class TestLegacyStarCursor:
    """Resuming from checkpoints left by the previous, named-stargazer collector."""

    @pytest.mark.parametrize(
        ("cursor", "expected"),
        [
            # Legacy GraphQL stargazer cursors, which embed the last collected ``starredAt``.
            ("Y3Vyc29yOnYyOpK0MjAyNi0wMy0xMlQxNjoyMTo0M1rOJ9tudA==", date(2026, 3, 12)),
            ("Y3Vyc29yOnYyOpK0MjAxOS0wOC0xOFQyMzozMDowOFrOCuY94Q==", date(2019, 8, 18)),
            ("bm90LWEtY3Vyc29y", None),  # valid base64, no timestamp
            ("not base64 !!", None),
        ],
    )
    def test_date_recovery(self, cursor, expected):
        """The last collected star date is read back out of a legacy cursor, if there is one."""
        assert (
            github_api.GitHubRepositoryCollectorGH._legacy_star_cursor_date(cursor)
            == expected
        )

    def test_caller_date_takes_precedence_over_cache(self, collector, monkeypatch):
        """Previously collected interactions are a better checkpoint than a stale cursor."""
        monkeypatch.setitem(
            github_api.PAGINATION_CACHE,
            "owner.name.stargazers",
            "Y3Vyc29yOnYyOpK0MjAyNi0wMy0xMlQxNjoyMTo0M1rOJ9tudA==",
        )
        assert collector._star_checkpoint("owner/name", date(2026, 6, 1)) == date(
            2026, 6, 1
        )

    def test_falls_back_to_cached_cursor(self, collector, monkeypatch):
        """Without collected interactions, the legacy cursor says where the named stargazers stopped."""
        monkeypatch.setitem(
            github_api.PAGINATION_CACHE,
            "owner.name.stargazers",
            "Y3Vyc29yOnYyOpK0MjAyNi0wMy0xMlQxNjoyMTo0M1rOJ9tudA==",
        )
        assert collector._star_checkpoint("owner/name", None) == date(2026, 3, 12)

    def test_no_checkpoint_available(self, collector):
        """A repository never collected before has no checkpoint."""
        assert collector._star_checkpoint("unknown/repo", None) is None


class TestPaginateStars:
    """Walking the star history backwards from the most recent week."""

    def test_one_record_per_star_oldest_first(self, collector, stub_history):
        """Counts are expanded into one record per star, indexed within the day."""
        stub_history([week_bucket(date(2020, 5, 3), [0, 2, 0, 0, 1, 0, 0])])
        assert collector._paginate_stars("owner/name") == [
            {"date": date(2020, 5, 4), "index": 0},
            {"date": date(2020, 5, 4), "index": 1},
            {"date": date(2020, 5, 7), "index": 0},
        ]

    def test_pages_back_to_repository_creation(self, collector, stub_history):
        """Without a checkpoint, paging continues until the history runs out."""
        weeks = [
            week_bucket(date(2020, 5, 24) - timedelta(weeks=i), [1, 0, 0, 0, 0, 0, 0])
            for i in range(5)
        ]
        calls = stub_history(weeks)
        assert len(collector._paginate_stars("owner/name")) == 5
        # Three full pages of two, then an empty page marking the end of the history.
        assert calls == [1, 2, 3, 4]

    def test_stops_at_checkpoint(self, collector, stub_history):
        """Paging stops on the page that reaches back past the checkpoint."""
        weeks = [
            week_bucket(date(2020, 5, 24) - timedelta(weeks=i), [1, 0, 0, 0, 0, 0, 0])
            for i in range(5)
        ]
        calls = stub_history(weeks)
        stars = collector._paginate_stars("owner/name", date(2020, 5, 10))
        assert [star["date"] for star in stars] == [
            date(2020, 5, 17),
            date(2020, 5, 24),
        ]
        # The second page reaches back past the checkpoint, so the remaining pages are not fetched.
        assert calls == [1, 2]

    def test_excludes_the_checkpoint_day_itself(self, collector, stub_history):
        """The checkpoint day is already collected, so its stars are not collected again."""
        stub_history([week_bucket(date(2020, 5, 3), [0, 2, 0, 0, 1, 0, 0])])
        stars = collector._paginate_stars("owner/name", date(2020, 5, 4))
        assert [star["date"] for star in stars] == [date(2020, 5, 7)]

    def test_excludes_the_current_day(self, collector, stub_history):
        """Today is still accumulating stars, so it is left until the next run."""
        today = datetime.now(UTC).date()
        week_start = today - timedelta(days=(today.weekday() + 1) % 7)
        stub_history(
            [
                week_bucket(week_start, [1] * 7),
                week_bucket(week_start - timedelta(weeks=1), [1] * 7),
            ]
        )
        collected = [star["date"] for star in collector._paginate_stars("owner/name")]
        assert today not in collected
        assert today - timedelta(days=1) in collected

    def test_handles_failed_request(self, collector, monkeypatch):
        """A failed request yields no stars rather than raising."""
        client = type(
            "Client",
            (),
            {"execute_rest_query": staticmethod(lambda path, params=None: None)},
        )()
        monkeypatch.setattr(collector, "client", client, raising=False)
        assert collector._paginate_stars("owner/name") == []

    def test_stops_at_pagination_limit(self, collector, stub_history, monkeypatch):
        """Paging gives up at the API's page limit rather than looping forever."""
        monkeypatch.setattr(github_api, "STAR_HISTORY_MAX_PAGES", 2)
        weeks = [
            week_bucket(date(2020, 5, 24) - timedelta(weeks=i), [1, 0, 0, 0, 0, 0, 0])
            for i in range(10)
        ]
        calls = stub_history(weeks)
        assert len(collector._paginate_stars("owner/name")) == 4
        assert calls == [1, 2]


class TestParseStarData:
    """Turning anonymous star counts into interaction records."""

    def test_anonymous_username_and_day_index(self, collector):
        """Stars have no user, so they get a placeholder username and their index within the day."""
        assert collector._parse_star_data({"date": date(2020, 5, 4), "index": 1}) == {
            "interaction": "stargazer",
            "username": github_api.ANONYMOUS_USERNAME,
            "number": 1,
            "created": date(2020, 5, 4),
        }

    def test_same_day_stars_survive_deduplication(self, collector):
        """The day index is what keeps otherwise-identical stars distinct downstream."""
        stars = [
            collector._parse_star_data({"date": date(2020, 5, 4), "index": index})
            for index in range(3)
        ]
        assert len(pd.DataFrame(stars).drop_duplicates()) == 3


class TestStarsCollectedThrough:
    """Deriving the star collection checkpoint from previously collected interactions."""

    @pytest.fixture
    def interactions(self):
        """Collected interactions spanning two repositories."""
        return pd.DataFrame(
            [
                {
                    "username": "anonymous",
                    "interaction": "stargazer",
                    "created": "2026-01-05",
                    "repo": "gh:a/b",
                },
                {
                    "username": "anonymous",
                    "interaction": "stargazer",
                    "created": "2026-03-11",
                    "repo": "gh:a/b",
                },
                {
                    "username": "someone",
                    "interaction": "commit",
                    "created": "2026-06-01",
                    "repo": "gh:a/b",
                },
                {
                    "username": "anonymous",
                    "interaction": "stargazer",
                    "created": "2026-08-09",
                    "repo": "gh:c/d",
                },
            ]
        )

    def test_latest_star_for_repo(self, interactions):
        """The checkpoint is the most recent star collected for the repository."""
        assert get_repo_interactions.get_latest_date_of_named_stargazers(
            interactions, "gh:a/b"
        ) == date(2026, 3, 11)

    def test_ignores_other_repos(self, interactions):
        """Each repository is checkpointed independently."""
        assert get_repo_interactions.get_latest_date_of_named_stargazers(
            interactions, "gh:c/d"
        ) == date(2026, 8, 9)

    def test_repo_without_stars(self, interactions):
        """A repository with no collected stars has no checkpoint."""
        assert (
            get_repo_interactions.get_latest_date_of_named_stargazers(
                interactions, "gh:e/f"
            )
            is None
        )

    def test_empty_interactions(self):
        """Nothing collected yet means no checkpoint."""
        empty = pd.DataFrame(columns=get_repo_interactions.COLS)
        assert (
            get_repo_interactions.get_latest_date_of_named_stargazers(empty, "gh:a/b")
            is None
        )
