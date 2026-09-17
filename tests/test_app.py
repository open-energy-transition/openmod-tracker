# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Streamlit app test suite."""

import datetime
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path("website").absolute()
MAIN_PAGE = "⚡️_Tool_Repository_Metrics.py"

# Add to PATH so that the relative import of `util.py` works in the app
sys.path.append(str(APP_PATH))


def get_file_paths() -> list[str]:
    """Get a list of file paths for the main page + each page in the pages folder."""
    page_folder = APP_PATH / "pages"
    page_files = page_folder.glob("*.py")
    file_paths = [str(file.absolute().relative_to(APP_PATH)) for file in page_files]
    return [MAIN_PAGE] + file_paths


@pytest.mark.limit_memory("500 MB", current_thread_only=True)
@pytest.mark.parametrize("file_path", get_file_paths())
def test_smoke_page(file_path):
    """Basic test to check against memory limits."""
    at = AppTest.from_file(APP_PATH / file_path, default_timeout=100).run()
    assert not at.exception


class TestMainPageSessionState:
    """Test main page with different session states."""

    @pytest.fixture(scope="class")
    def main_page_app(self) -> AppTest:
        """Create main page app instance."""
        return AppTest.from_file(APP_PATH / MAIN_PAGE, default_timeout=100).run()

    @pytest.mark.parametrize(
        "toggle_key",
        [
            "Docs",
            "Dependents",
            "1 Month Downloads",
            "Category",
            "Stars",
            "Contributors",
            "DDS",
            "Forks",
        ],
    )
    def test_nan_filter_toggles(self, main_page_app: AppTest, toggle_key: str):
        """Test toggling NaN filters for columns that actually have missing data."""
        at = main_page_app
        # Find the toggle by key (only exists if column has missing data)
        try:
            toggle = at.toggle(key=f"exclude_nan_{toggle_key}")
            at = toggle.set_value(True).run()
        except KeyError:
            # Toggle doesn't exist because column has no missing data
            pytest.skip(f"Toggle {toggle_key} not present (no missing data)")

    @pytest.mark.parametrize(
        "key",
        ["Stars", "Contributors", "DDS", "Forks", "Dependents", "1 Month Downloads"],
    )
    def test_range_sliders(self, main_page_app: AppTest, key: str):
        """Test adjusting each range slider."""
        at = main_page_app
        slider_key = f"slider_{key}"
        slider = at.slider(key=slider_key)

        # For numeric sliders, work directly with the numeric values
        min_val, max_val = slider.min, slider.max
        quarter = (max_val - min_val) / 4
        new_range = (min_val + quarter, max_val - quarter)

        # Set to a subset of the range
        at = slider.set_value(new_range).run()
        # Get slider again after rerun
        slider = at.slider(key=slider_key)
        # Reset to full range
        slider.set_value((min_val, max_val)).run()

    @pytest.mark.parametrize("key", ["Created", "Updated"])
    def test_range_sliders_dt(self, main_page_app: AppTest, key: str):
        """Test adjusting each datetime range slider."""
        at = main_page_app
        slider_key = f"slider_{key}"
        slider = at.slider(key=slider_key)

        # For date sliders, need to convert min/max to date objects
        # (AppTest returns timestamp floats but expects date objects for set_value)

        min_val = datetime.date.fromtimestamp(slider.min / 1_000_000)
        max_val = datetime.date.fromtimestamp(slider.max / 1_000_000)
        days_range = (max_val - min_val).days
        quarter_days = days_range // 4
        new_range = (
            min_val + datetime.timedelta(days=quarter_days),
            max_val - datetime.timedelta(days=quarter_days),
        )
        # Set to a subset of the range
        at = slider.set_value(new_range).run()
        # Get slider again after rerun
        slider = at.slider(key=slider_key)
        # Reset to full range
        slider.set_value((min_val, max_val)).run()

    @pytest.mark.parametrize(
        "multiselect_key", ["multiselect_Category", "multiselect_Language"]
    )
    def test_categorical_multiselects(
        self, main_page_app: AppTest, multiselect_key: str
    ):
        """Test categorical multiselect filters."""
        at = main_page_app
        multiselect = at.multiselect(key=multiselect_key)
        # Select just first option
        at = multiselect.set_value([multiselect.options[0]]).run()
        # Get multiselect again after rerun
        multiselect = at.multiselect(key=multiselect_key)
        # Reset to all options
        multiselect.set_value(multiselect.options).run()

    def test_proprietary_language_toggle(self, main_page_app: AppTest):
        """Test the proprietary language exclusion toggle."""
        at = main_page_app
        toggle = at.toggle(key="exclude_proprietary")
        # Toggle off (include proprietary)
        at = toggle.set_value(False).run()
        # Get toggle again after rerun
        toggle = at.toggle(key="exclude_proprietary")
        # Toggle back on (exclude proprietary)
        toggle.set_value(True).run()


# Note: The old user analysis and dev metrics pages have been unified into
# a single Tool Deep Dive page. The unified page has a different structure
# (tab-based and requires session state with selected tools), making it
# impractical to test the same way. The smoke test already covers the new page.
