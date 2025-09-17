# SPDX-FileCopyrightText: openmod-tracker contributors listed in AUTHORS.md
#
# SPDX-License-Identifier: MIT


"""Utility functions to support user analysis."""

from pathlib import Path

import yaml


def read_yaml(filename: str | Path, exists: bool = True) -> dict:
    """Read YAML config file.

    Args:
        filename (str | Path): The name of the YAML file to read.
        exists (bool): If True, raise an error if the file does not exist, otherwise return an empty dict.

    Returns:
        dict: The contents of the YAML file as a dictionary.
    """
    try:
        yaml_dict = yaml.safe_load(
            (Path(__file__).parent / "config" / filename)
            .with_suffix(".yaml")
            .read_text()
        )
    except FileNotFoundError:
        if exists:
            raise FileNotFoundError(f"Config file {filename} not found")
        else:
            yaml_dict = {}
    return yaml_dict


def dump_yaml(filename: str | Path, data: dict):
    """Dump dict to yaml config file."""
    (Path(__file__).parent / "config" / filename).with_suffix(".yaml").write_text(
        yaml.safe_dump(data, sort_keys=True)
    )
