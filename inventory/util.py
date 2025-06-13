"""Various util functions for inventory collection, filtering, and stats getting."""

import logging
import time
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


def get_ecosystems_repo_data(url: str, attempt: int = 1) -> dict | None:
    """Get repository lookup API call response from ecosyste.ms based on the provided repo URL.

    Args:
        url (str): Git repo URL.
        attempt (int):
            Tracks the number of attempts at checking this URL.
            We use this to avoid stressing the ecosyste.ms servers with reattempts after possible timeouts.
            Defaults to False.

    Returns:
        requests.Response: Content of data for `url`.
    """
    safe_query = get_safe_url_string(url)

    response = requests.get(ECOSYSTEMS_REPO_LOOKUP_API + safe_query)
    if response.ok:
        return yaml.safe_load(response.content.decode("utf-8"))
    elif response.status_code == "500" and attempt == 1:
        # Likely a timeout, let's try again
        LOGGER.warning(
            "Problem communicating with ecosyste.ms; trying again in 10 seconds."
        )
        time.sleep(10)
        return get_ecosystems_repo_data(url, 2)
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
