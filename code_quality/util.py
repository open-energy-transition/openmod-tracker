# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Utility functions for the scripts.

Common helper functions shared across multiple scripts in the project.
"""

import datetime


def log_to_file(log_file, status, message):
    """Write a timestamped log entry to a file.

    Args:
        log_file (str): Path to the log file
        status (str): Status code for the log entry
                     (e.g., "SYNC", "SYNC-FAILED")
        message (str): Log message to write

    Returns:
        None
    """
    if not log_file:
        return

    with open(log_file, "a") as log:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"[{status}] {message} at {timestamp}\n")
