"""Utility functions to support user analysis."""

from pathlib import Path

import yaml


def read_yaml(filename: str | Path) -> dict:
    """Read YAML config file."""
    return yaml.safe_load(
        (Path(__file__).parent / "config" / filename).with_suffix(".yaml").read_text()
    )


def dump_yaml(filename: str | Path, data: dict):
    """Dump dict to yaml config file."""
    (Path(__file__).parent / "config" / filename).with_suffix(".yaml").write_text(
        yaml.safe_dump(data, sort_keys=True)
    )
