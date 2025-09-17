# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT


"""GitHub user classifier.

Modified from https://github.com/dpaolella/open-model-analysis/blob/76201927de5a64ed4b6cd20e197e4b58abe7095b/github_user_analyzer.py

(C) David Paolella
License: MIT

(C) Open Energy Transition (OET)
License: MIT / CC0 1.0
"""

import re
import time
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import click
import pandas as pd
import pycountry
import requests
import unidecode
import util
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from tqdm import tqdm

CLASSIFICATION = util.read_yaml("classification")
ORG_MAPPING = util.read_yaml("org_mapping")
EMAIL_DOMAIN_MAPPING = util.read_yaml("email_domains")
COUNTRY_MAPPING = util.read_yaml("country_mapping")
GECODE_CACHE = util.read_yaml("geocode_cache", exists=False)

ACADEMIC_EMAIL_DOMAINS = requests.get(
    "https://raw.githubusercontent.com/Hipo/university-domains-list/refs/heads/master/world_universities_and_domains.json"
).json()
DEFAULT_COMPANY_CLASSIFICATION = "professional"


def classify_user(user_data: pd.Series):
    """Classify users into categories: research, industry, utility, etc."""
    # Default classification
    classifications: dict[str, list] = defaultdict(list)
    # Check for company/organization hints
    if user_data["company"]:
        classifications["company"] = [
            i for org in user_data["company"] for i in classify_company(org)
        ]

    if pd.notnull(user_data["email_domain"]):
        classifications["email_domain"] = classify_email_domain(
            user_data["email_domain"], "cat"
        )

    if pd.notnull(user_data["blog"]):
        classifications["blog"] = classify_email_domain(
            urlparse(user_data["blog"]).netloc, "cat"
        )

    if pd.notnull(user_data["bio"]) | pd.notnull(user_data["readme"]):
        classifications["bio"] = classify_company(
            (str(user_data["bio"]) + " " + str(user_data["readme"])).lower().strip()
        )
    classification = resolve_classifications(
        classifications, ["email_domain", "company", "blog", "bio"]
    )
    if not classification and user_data["company"]:
        classification = DEFAULT_COMPANY_CLASSIFICATION
    return "unknown" if not classification else classification


def classify_country(user_data: pd.Series) -> str | None:
    """Classify country according to referenced email / URL domains."""
    classifications: dict[str, list] = defaultdict(list)
    if pd.notnull(user_data["email_domain"]):
        classifications["email_domain"] = classify_email_domain(
            user_data["email_domain"], "country"
        )

    if pd.notnull(user_data["blog"]):
        classifications["blog"] = classify_email_domain(
            urlparse(user_data["blog"]).netloc, "country"
        )
    classification = resolve_classifications(classifications, ["email_domain", "blog"])
    return classification


def resolve_classifications(
    classifications: dict[str, list], priority: list[str]
) -> str | None:
    """Resolve a list of classifications by selecting the one(s) that are most relevant according to a given priority order.

    Iterating in order of priority:
        1. If the first classification source in the priority order gives a single classification,
           that will be taken as "truth" and all other sources will be ignored.
        2. If a source gives multiple classifications, the next source in the priority order will be intersected with it.
           E.g. [industry, professional] and [industry, government] from two sources will resolve to industry.
        3. If a list of classifications still exists after scanning the full priority order,
           the result will be a comma separated list of the remaining classifications.

    Args:
        classifications (dict[str, list]): key = classification source (e.g. company name), value = list of possible classifications
        priority (list[str]): Prioritisation of classification source in resolving the classification (earlier in list == higher priority)

    Returns:
        str | None: If no classifications given in any source, returns None.
    """
    current_options = set(classifications[priority[0]]) - set([None])
    for param in priority:
        new_options = set(classifications[param]) - set([None])
        if len(current_options) == 0:
            current_options = new_options
        if len(current_options) == 1:
            break
        if len(new_options) == 0:
            continue
        else:
            current_options = current_options.intersection(new_options)
    if len(current_options) == 0:
        return None
    else:
        return ",".join(sorted(current_options))


def classify_academic_email_domain(domain: str) -> list[dict[str, str]]:
    """Classify an email domain as academic by checking it against an academic email domain database.

    Args:
        domain (str): email domain (the string after the "@" of an email.)

    Returns:
        list[dict[str, str]]: If the domain is found in the database, returns the associated configuration dictionary/ies, otherwise returns an empty dictionary.
    """
    result = [
        i
        for i in ACADEMIC_EMAIL_DOMAINS
        if any(domain.endswith(j) for j in i["domains"])
    ]
    # We always just take the first result
    return result if result else [{}]


def classify_email_domain(
    domain: str, extract: Literal["cat", "country"]
) -> list[str | None]:
    """Classify an email domain.

    Args:
        domain (str): email domain (the string after the "@" of an email.) or the TLD of a URL.
        extract (Literal[cat, country]): If "cat", will return the classification (academic, government, etc.). If "country", will return the country of the associated domain.

    Returns:
        list[str | None]: If found (multiple possible), returns list of categories / countries. Otherwise returns list containing a None.
    """
    if not domain:
        return [None]

    classified_academic = classify_academic_email_domain(domain)

    if classified_academic != [{}]:
        if extract == "cat":
            return ["academic"]
        else:
            return [i.get(extract, None) for i in classified_academic]

    classified: list = []
    for cat, cat_maps in EMAIL_DOMAIN_MAPPING.items():
        for option in cat_maps.get("match", {}):
            if any(domain.endswith(i) for i in option["email_domain"]):
                classified.append(cat if extract == "cat" else option[extract])
    return classified


def classify_company(company: str) -> list[str]:
    """Classify based on company name."""
    classified: list = []
    for cat, cat_maps in CLASSIFICATION.items():
        if any(company == i for i in cat_maps["match"]):
            classified.append(cat)
    for cat, cat_maps in CLASSIFICATION.items():
        if not classified and any(
            _search_whole_word_substrings(i, company) for i in cat_maps["match"]
        ):
            classified.append(cat)
    for cat, cat_maps in CLASSIFICATION.items():
        if not classified and any(
            _search_whole_word_substrings(i, company) for i in cat_maps["keyword"]
        ):
            classified.append(cat)

    return classified


def _search_whole_word_substrings(substring: str, text: str) -> bool:
    result = re.search(rf"\b{substring}\b", text)
    if result is not None:
        return True
    else:
        return False


def map_org_name(org_name: str) -> list[str]:
    """Normalize an organization name to a standard form.

    The name will be cleaned and then compared against our mapping config to convert it to a standardised form.
    If it doesn't exist in our mapping config, the cleaned name will be returned as-is.
    """
    # Create normalized version (lowercase, no punctuation, normalized whitespace)
    normalized = org_name.lower().replace("@", " ").strip()
    normalized = " ".join(normalized.split())  # Normalize whitespace
    normalized = unidecode.unidecode(normalized)  # remove accents

    # Next, try exact matches on name/short name
    mapped = [
        i["name"]
        for i in ORG_MAPPING
        if any(normalized == i.get(key, None) for key in ["name", "shortname"])
    ]
    if mapped:
        return mapped

    # Next, try exact matches on variations
    mapped = [
        i["name"]
        for i in ORG_MAPPING
        if any(normalized == var for var in i.get("variations", []))
    ]
    if mapped:
        return mapped

    # Next, try fuzzy matches on name/short name
    mapped = [
        i["name"]
        for i in ORG_MAPPING
        if any(
            key in i and _search_whole_word_substrings(i[key], normalized)
            for key in ["name", "shortname"]
        )
    ]
    if mapped:
        return mapped

    # Next, try fuzzy matches on variations
    mapped = [
        i["name"]
        for i in ORG_MAPPING
        if any(
            _search_whole_word_substrings(var, normalized)
            for var in i.get("variations", [])
        )
    ]
    if mapped:
        return mapped

    return [normalized]


# Function to geocode locations
def geocode_locations(locations: Iterable[str]):
    """Geocode a dictionary of location strings to countries."""
    # Initialize geolocator
    geolocator = Nominatim(user_agent="esm-tool-analyzer")

    # Process locations
    geocode_locations = set(locations) - GECODE_CACHE.keys()
    # First try to extract countries using pattern matching
    disable_tqdm = len(geocode_locations) < 2
    if geocode_locations:
        for location in tqdm(
            geocode_locations,
            desc="Extracting countries by string matching",
            disable=disable_tqdm,
        ):
            country = extract_country(location)
            if country is not None:
                GECODE_CACHE[location] = country

    geocode_locations -= GECODE_CACHE.keys()
    disable_tqdm = len(geocode_locations) < 2
    # Then try geocoding for locations without a country
    if geocode_locations:
        for location in tqdm(
            geocode_locations,
            desc="Extracting countries by geocoding",
            disable=disable_tqdm,
        ):
            start = int(time.time())
            try:
                # Try geocoding with a timeout
                geo = geolocator.geocode(location, timeout=5, language="en")
                if geo and geo.raw.get("display_name"):
                    # Extract country from geocoded result
                    addr_parts = geo.raw.get("display_name", "").split(",")
                    if addr_parts:
                        country = addr_parts[-1].strip()
                        GECODE_CACHE[location] = country
            except (GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError):
                # Skip if geocoding fails
                pass
            elapsed = int(time.time()) - start
            # Nomatim has a maximum of 1 request per second
            if elapsed < 1:
                time.sleep(1 - elapsed)
        remaining_locations = geocode_locations - GECODE_CACHE.keys()
        for location in remaining_locations:
            GECODE_CACHE[location] = None


# Helper function to extract country from location string
def extract_country(location: str) -> str | None:
    """Extract country from a location string using pattern matching and common names."""
    # Common country names and abbreviations

    # Try direct mapping first
    loc_lower = location.lower()
    if loc_lower in COUNTRY_MAPPING:
        return COUNTRY_MAPPING[loc_lower]

    # Handle cases like "City, Country"
    parts = [p.strip() for p in location.split(",")]
    if len(parts) > 1:
        last_part = parts[-1].lower()
        if last_part in COUNTRY_MAPPING:
            return COUNTRY_MAPPING[last_part]
    try:
        country_data = pycountry.countries.lookup(loc_lower)
        return country_data.name
    except LookupError:
        return None


def query_geocode_cache(user_data: pd.Series) -> str | None:
    """Get data from the geocode country cache dict, returning an attempt at geolocating using email domains if no data is in the cache."""
    cached_location = GECODE_CACHE.get(user_data["location"])
    if pd.isnull(cached_location):
        return classify_country(user_data)
    else:
        return cached_location


@click.command()
@click.option(
    "--user-details",
    type=click.Path(exists=True, dir_okay=False, file_okay=True, path_type=Path),
    help="Path to the user_details.csv file (from get_user_details.py).",
    default="user_analysis/output/user_details.csv",
)
@click.option(
    "--out-path",
    type=click.Path(exists=False, dir_okay=False, file_okay=True, path_type=Path),
    help="Output directory for user classifications.",
    default="user_analysis/output/user_classifications.csv",
)
def cli(user_details: Path, out_path: Path):
    """Main function for analyzing GitHub user data."""
    # Parse command line arguments
    user_df = pd.read_csv(user_details, index_col=0)
    geocode_locations(user_df.location.dropna().unique())
    user_dict = []
    for username, user_data in tqdm(
        user_df.iterrows(), desc="Classifying users", total=len(user_df)
    ):
        company = user_data["company"]
        if pd.isnull(company) and pd.notnull(user_data["email_domain"]):
            # For simplicity, we just take the first result (there _could_ be several)
            company = classify_academic_email_domain(user_data["email_domain"])[0].get(
                "name", None
            )
        mapped_company = map_org_name(company) if pd.notnull(company) else []
        user_data["company"] = mapped_company
        location = query_geocode_cache(user_data)
        if not pd.isnull(location) and user_data["company"]:
            geocode_locations(user_data["company"])
            location = query_geocode_cache(user_data)

        user_dict.append(
            {
                "username": username,
                "classification": classify_user(user_data),
                "company": ",".join(user_data["company"]),
                "location": query_geocode_cache(user_data),
                "repos": user_data.repos,
            }
        )
    util.dump_yaml("geocode_cache", GECODE_CACHE)
    classification_df = pd.DataFrame(user_dict)
    classification_df.sort_values("username").to_csv(out_path, index=False)


if __name__ == "__main__":
    cli()
