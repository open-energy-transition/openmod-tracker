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

    def test_custom_scoring_toggle(self, main_page_app: AppTest):
        """Test toggling custom scoring on and off."""
        at = main_page_app
        # Toggle scoring on
        score_toggle = at.toggle(key="score_toggle")
        at = score_toggle.set_value(True).run()

        # Test scoring method selectbox
        scoring_method = at.selectbox(key="scoring_method")
        at = scoring_method.set_value("min-max").run()
        scoring_method = at.selectbox(key="scoring_method")
        at = scoring_method.set_value("rank").run()

        # Toggle scoring off
        score_toggle = at.toggle(key="score_toggle")
        score_toggle.set_value(False).run()

    @pytest.mark.parametrize(
        "column",
        ["Stars", "Contributors", "DDS", "Forks", "Dependents", "1 Month Downloads"],
    )
    def test_scoring_weights(self, main_page_app: AppTest, column: str):
        """Test adjusting scoring weights for each metric."""
        at = main_page_app
        # First enable scoring
        score_toggle = at.toggle(key="score_toggle")
        at = score_toggle.set_value(True).run()

        # Adjust the weight for this column
        weight_key = f"scoring_{column}"
        number_input = at.number_input(key=weight_key)
        at = number_input.set_value(0.8).run()


class TestUserAnalysisPageSessionState:
    """Test user analysis page with different session states."""

    @pytest.fixture(scope="class")
    def user_analysis_app(self) -> AppTest:
        """Create user analysis page app instance."""
        page_path = "pages/1_👤_Deep_Dive_-_User_Interaction_Analysis.py"
        return AppTest.from_file(APP_PATH / page_path, default_timeout=100).run()

    def test_all_tools_toggle(self, user_analysis_app: AppTest):
        """Test toggling between all tools and subset selection."""
        at = user_analysis_app
        # Get the all tools toggle from sidebar
        all_tools_toggle = at.sidebar.toggle[0]

        # Toggle to show analysis for subset
        at = all_tools_toggle.set_value(False).run()

        # Try selecting specific tools
        tool_multiselect = at.sidebar.multiselect[0]
        # Select first two tools
        tools_to_select = tool_multiselect.options[:2]
        at = tool_multiselect.set_value(tools_to_select).run()

        # Toggle back to all tools
        all_tools_toggle = at.sidebar.toggle[0]
        all_tools_toggle.set_value(True).run()

    def test_single_tool_selection(self, user_analysis_app: AppTest):
        """Test selecting a single tool for analysis."""
        at = user_analysis_app
        all_tools_toggle = at.sidebar.toggle[0]
        at = all_tools_toggle.set_value(False).run()

        tool_multiselect = at.sidebar.multiselect[0]
        # Select just one tool
        tool_multiselect.set_value([tool_multiselect.options[0]]).run()


class TestDevMetricsPageSessionState:
    """Test development metrics page with different session states."""

    @pytest.fixture(scope="class")
    def dev_metrics_app(self) -> AppTest:
        """Create development metrics page app instance."""
        page_path = "pages/2_📊_Deep_Dive_-_Project_Development_Metrics.py"
        return AppTest.from_file(APP_PATH / page_path, default_timeout=100).run()

    def test_all_tools_toggle(self, dev_metrics_app: AppTest):
        """Test toggling between all tools and subset selection."""
        at = dev_metrics_app
        # Get the all tools toggle from sidebar
        all_tools_toggle = at.sidebar.toggle[0]

        # Toggle to show analysis for subset
        at = all_tools_toggle.set_value(False).run()

        # Try selecting specific tools
        tool_multiselect = at.sidebar.multiselect[0]
        # Select a subset of tools
        tools_to_select = tool_multiselect.options[:3]
        at = tool_multiselect.set_value(tools_to_select).run()

        # Toggle back to all tools
        all_tools_toggle = at.sidebar.toggle[0]
        all_tools_toggle.set_value(True).run()

    def test_bot_interactions_toggle(self, dev_metrics_app: AppTest):
        """Test toggling bot interactions on/off."""
        at = dev_metrics_app
        # Find the hide bots checkbox
        hide_bots = at.checkbox(key="hide_bots_checkbox")
        # Include bots
        at = hide_bots.set_value(False).run()
        # Get checkbox again after rerun
        hide_bots = at.checkbox(key="hide_bots_checkbox")
        # Exclude bots
        hide_bots.set_value(True).run()

    @pytest.mark.parametrize("resolution", ["Daily", "Weekly", "Monthly"])
    def test_time_resolution_toggle(self, dev_metrics_app: AppTest, resolution: str):
        """Test toggling between different time resolutions."""
        at = dev_metrics_app
        time_resolution = at.radio(key="time_resolution_filter")
        time_resolution.set_value(resolution).run()

    def test_cumulative_toggle(self, dev_metrics_app: AppTest):
        """Test toggling cumulative data on/off."""
        at = dev_metrics_app
        cumulative = at.toggle(key="cumulative_toggle")
        # Turn off cumulative
        at = cumulative.set_value(False).run()
        # Get toggle again after rerun
        cumulative = at.toggle(key="cumulative_toggle")
        # Turn on cumulative
        cumulative.set_value(True).run()

    def test_date_range_slider(self, dev_metrics_app: AppTest):
        """Test adjusting the date range slider."""
        at = dev_metrics_app
        date_slider = at.slider(key="date_range_slider_dev")

        # For date sliders, convert timestamp floats to date objects
        min_val = datetime.date.fromtimestamp(date_slider.min / 1_000_000)
        max_val = datetime.date.fromtimestamp(date_slider.max / 1_000_000)
        days_range = (max_val - min_val).days
        quarter_days = days_range // 4
        new_range = (
            min_val + datetime.timedelta(days=quarter_days),
            max_val - datetime.timedelta(days=quarter_days),
        )

        at = date_slider.set_value(new_range).run()

        # Get slider again after rerun
        date_slider = at.slider(key="date_range_slider_dev")
        # Reset to full range
        date_slider.set_value((min_val, max_val)).run()

    def test_combined_filters(self, dev_metrics_app: AppTest):
        """Test combining multiple filters together."""
        at = dev_metrics_app

        # Disable all tools toggle and select specific tools
        all_tools_toggle = at.sidebar.toggle[0]
        at = all_tools_toggle.set_value(False).run()

        tool_multiselect = at.sidebar.multiselect[0]
        at = tool_multiselect.set_value([tool_multiselect.options[0]]).run()

        # Change time resolution
        time_resolution = at.radio(key="time_resolution_filter")
        at = time_resolution.set_value("Monthly").run()

        # Toggle cumulative off
        cumulative = at.toggle(key="cumulative_toggle")
        at = cumulative.set_value(False).run()

        # Toggle bots on
        hide_bots = at.checkbox(key="hide_bots_checkbox")
        hide_bots.set_value(False).run()
