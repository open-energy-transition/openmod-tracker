# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Streamlit app test suite."""

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


@pytest.mark.parametrize("file_path", get_file_paths())
def test_smoke_page(file_path):
    """This will run a basic test on each page in the pages folder to check that no exceptions are raised while the app runs."""
    at = AppTest.from_file(APP_PATH / file_path, default_timeout=100).run()
    assert not at.exception
