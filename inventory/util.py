# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""Various util functions for inventory collection, filtering, and stats getting."""

import logging
from pathlib import Path
from urllib.parse import quote_plus

import requests
import yaml

ECOSYSTEMS_REPO_LOOKUP_API = "https://repos.ecosyste.ms/api/v1/repositories/lookup?url="
ECOSYSTEMS_PACKAGES_LOOKUP_API = (
    "https://packages.ecosyste.ms/api/v1/packages/lookup?repository_url="
)

LOGGER = logging.getLogger(__name__)


def get_url_json_content(url: str) -> dict:
    """Stream content of a URL containing YAML/JSON data to a dictionary.

    Args:
        url (str): Database / file URL.

    Returns:
        dict: Content of data at `url`.
    """
    response = requests.get(url)
    content = response.content.decode("utf-8")
    return yaml.safe_load(content)


def get_ecosystems_data(url: str) -> list[dict] | dict | str | None:
    """Get repository API string from ecosyste.ms based on the provided repo URL.

    Args:
        url (str): Git repo URL.

    Returns:
        requests.Response: If the repository exists, the ecosyste.ms API repository URL
    """
    response = requests.get(url)

    if response.ok:
        return yaml.safe_load(response.content.decode("utf-8"))
    elif response.status_code != 500:
        LOGGER.warning(f"Static URL {url} returned {response.status_code} status code.")
        return "not-found"
    else:
        return None


def get_ecosystems_repo_data(url: str) -> dict | str | None:
    """Get repository lookup API call response from ecosyste.ms based on the provided API repository URL.

    Args:
        url (str): ecosyste.ms API repo URL.

    Returns:
        requests.Response: Content of data for `url`.
    """
    ECOSYSTEMS_CACHE = read_cache("ecosystems_urls")
    ems_url = ECOSYSTEMS_CACHE.get(url, None)

    if ems_url == "not-found":
        ems_data = ems_url

    elif ems_url is None:
        safe_query = get_safe_url_string(url)
        ems_data = get_ecosystems_data(ECOSYSTEMS_REPO_LOOKUP_API + safe_query)
        if isinstance(ems_data, dict):
            cache_entry = ems_data["repository_url"]
        else:
            cache_entry = ems_data
        ECOSYSTEMS_CACHE[url] = cache_entry
        dump_cache("ecosystems_urls", ECOSYSTEMS_CACHE)

    else:
        ems_data = get_ecosystems_data(ems_url)

    return ems_data


def get_ecosystems_package_data(url: str) -> requests.Response:
    """Get package lookup API call response from ecosyste.ms based on the provided repo URL.

    Args:
        url (str): Git repo URL.

    Returns:
        requests.Response: Content of data for packages linked to `url`.
    """
    safe_query = get_safe_url_string(url)
    package_data = get_ecosystems_data(ECOSYSTEMS_PACKAGES_LOOKUP_API + safe_query)
    if package_data and package_data != "not-found":
        package_data = [
            src
            for src in package_data
            if (
                src["ecosystem"] != "go"
                or src.get("repo_metadata", {}).get("language", "").lower() == "go"
            )
        ]

    return package_data


def get_safe_url_string(url: str) -> str:
    """Encode special characters in URL prior to an API call.

    Args:
        url (str): URL string to encode.

    Returns:
        str: Encoded URL string.
    """
    return quote_plus(url)


def read_cache(filename: str) -> dict:
    """Read YAML cache file."""
    file = _filename_to_yaml_path(filename, "cache")
    if not file.exists():
        return {}
    else:
        return yaml.safe_load(file.read_text())


def dump_cache(filename: str, data: dict):
    """Dump dict to yaml cache file."""
    _filename_to_yaml_path(filename, "cache").write_text(
        yaml.safe_dump(data, sort_keys=True)
    )


def _filename_to_yaml_path(filename: str, dir: str) -> Path:
    """Convert a filename to a Path object relative to the current directory.

    Args:
        filename (str): YAML file name. Suffix will be coerced to `.yaml`, whether or not it is included in `filename`.
        dir (str): Subdirectory in which the file is found.

    Returns:
        Path: Path object pointing to `<util_dir>/<dir>/<filename>.yaml`
    """
    return (Path(__file__).parent / dir / filename).with_suffix(".yaml")
