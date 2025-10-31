# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Utility functions for the scripts.

Common helper functions shared across multiple scripts in the project.
"""

import logging
from pathlib import Path


def set_logging_handlers(logger: logging.Logger, log_file: Path | None = None):
    """Set up logging handlers for console and file output.

    Args:
        logger (logging.Logger): Logger instance to configure.
        log_file (Path | None):
            Optional path to a log file.
            If provided, log messages will also be written to this file.
    """
    logging.root.setLevel(logging.NOTSET)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
