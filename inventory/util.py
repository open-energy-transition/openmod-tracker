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
ECOSYSTEMS_CACHE_FILE = Path(__file__).parent / "ecosystems_urls.yaml"
ECOSYSTEMS_CACHE = (
    yaml.safe_load(ECOSYSTEMS_CACHE_FILE.read_text())
    if ECOSYSTEMS_CACHE_FILE.exists()
    else {}
)


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


def lookup_ecosystems_repo(url: str) -> str | None:
    """Get repository API string from ecosyste.ms based on the provided repo URL.

    Args:
        url (str): Git repo URL.

    Returns:
        requests.Response: If the repository exists, the ecosyste.ms API repository URL
    """
    safe_query = get_safe_url_string(url)
    response = requests.get(ECOSYSTEMS_REPO_LOOKUP_API + safe_query)

    if response.ok:
        return yaml.safe_load(response.content.decode("utf-8"))["repository_url"]
    elif response.status_code != "500":
        return "not-found"
    else:
        return None


def get_ecosystems_repo_data(url: str) -> dict | None:
    """Get repository lookup API call response from ecosyste.ms based on the provided API repository URL.

    Args:
        url (str): ecosyste.ms API repo URL.

    Returns:
        requests.Response: Content of data for `url`.
    """
    ems_url = ECOSYSTEMS_CACHE.get(url, None)
    if ems_url is None:
        ems_url = lookup_ecosystems_repo(url)
        ECOSYSTEMS_CACHE[url] = ems_url
        ECOSYSTEMS_CACHE_FILE.write_text(
            yaml.safe_dump(ECOSYSTEMS_CACHE, sort_keys=True)
        )
    if ems_url is None or ems_url == "not-found":
        return ems_url

    response = requests.get(ems_url)
    if response.ok:
        return yaml.safe_load(response.content.decode("utf-8"))
    else:
        return None


def get_ecosystems_package_data(url: str) -> requests.Response:
    """Get package lookup API call response from ecosyste.ms based on the provided repo URL.

    Args:
        url (str): Git repo URL.

    Returns:
        requests.Response: Content of data for packages linked to `url`.
    """
    safe_query = get_safe_url_string(url)

    return requests.get(ECOSYSTEMS_PACKAGES_LOOKUP_API + safe_query)


def get_safe_url_string(url: str) -> str:
    """Encode special characters in URL prior to an API call.

    Args:
        url (str): URL string to encode.

    Returns:
        str: Encoded URL string.
    """
    return quote_plus(url)
