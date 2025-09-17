# SPDX-FileCopyrightText: openmod-tracker contributors listed in AUTHORS.md
#
# SPDX-License-Identifier: MIT


"""Scripts and CLI to create SonarCloud projects and to retrieve statistics from analysed projects."""

import logging
import os
from pathlib import Path

import click
import dotenv
import pandas as pd
import requests
from github import Github
from tqdm import tqdm

PROVISION_API = "https://sonarcloud.io/api/alm_integration/provision_projects"
METRICS_API = "https://sonarcloud.io/api/measures/component"
BINDINGS_API = "https://api.sonarcloud.io/dop-translation/project-bindings"
PROJECTS_API = "https://sonarcloud.io/api/projects/search"

LOGGER = logging.getLogger(__name__)

dotenv.load_dotenv()


def sonarcloud_header() -> dict:
    """Returns the headers required for SonarCloud API requests."""
    return {"Authorization": "Bearer " + os.environ["SONARCLOUD_TOKEN"]}


def get_repo_id(owner: str, repo_name: str, token: str | None = None) -> int:
    """Returns the GitHub repository ID for the given owner and repo name.

    Args:
        owner (str): The owner of the GitHub repository.
        repo_name (str): The name of the GitHub repository.
        token (str | None): The GitHub token for authentication (optional).
    """
    gh_client = Github(token)
    repo = gh_client.get_repo(f"{owner}/{repo_name}")
    return repo.id


def get_analysed_repo_keys(owner: str) -> dict:
    """Retrieves all already analysed SonarCloud project keys for the specified organization.

    Args:
        owner (str): The GitHub organization name.

    Returns:
        dict: A dictionary mapping repository names to their SonarCloud project keys for the given organization.
    """
    page = 1
    params = {"organization": owner, "p": page, "ps": 500}
    keys = dict()
    response = requests.get(PROJECTS_API, params=params, headers=sonarcloud_header())
    while response.status_code == 200 and response.json().get("components"):
        components = response.json()["components"]
        for component in components:
            # Map the repo name to its key
            if "lastAnalysisDate" in component:
                keys[component["name"]] = component["key"]
            else:
                LOGGER.error(
                    f"Found repo which has not been analyzed yet: {component['name']}"
                )
        page += 1
        params["p"] = page
        response = requests.get(
            PROJECTS_API, params=params, headers=sonarcloud_header()
        )
    click.echo(
        f"Found {len(keys)} analysed SonarCloud project keys for organization {owner}."
    )
    return keys


def has_bindings(url: str) -> list:
    """Checks if a SonarCloud project is bound to a GitHub repository.

    Args:
        url (str): The URL of the GitHub repository.

    Returns:
        list: A list of bindings for the specified repository. If not bound, this list will be empty.
    """
    params = {"url": url}
    response = requests.get(BINDINGS_API, params=params, headers=sonarcloud_header())

    if response.status_code == 200:
        bindings = response.json()["bindings"]
    else:
        LOGGER.error(f"Failed to retrieve bindings for repo {url}: {response.text}")
        bindings = []
    return bindings


def create_project(owner: str, repo_name: str) -> str:
    """Creates a new SonarCloud project for the specified GitHub repository.

    Args:
        owner (str): The owner of the GitHub repository.
        repo_name (str): The name of the GitHub repository.

    Returns:
        str: The SonarCloud project key for the created project, or an empty string if creation failed.
    """
    repo_id = get_repo_id(owner, repo_name, os.environ.get("GITHUB_TOKEN", None))
    # Request parameters
    params = {
        "installationKeys": f"{owner}/{repo_name}|{repo_id}",
        "organization": owner,
    }

    # Make the request
    response = requests.post(PROVISION_API, data=params, headers=sonarcloud_header())
    if response.status_code == 200:
        projects = response.json()["projects"]
    else:
        LOGGER.error(
            f"Failed to create sonarcloud project for repo {repo_name}: {response.text}"
        )
        projects = []
    return projects[0]["projectKey"] if projects else ""


def get_project_stats(project_id: str, metrics: str) -> dict:
    """Retrieves the specified metrics for a SonarCloud project.

    Args:
        project_id (str): The ID of the SonarCloud project.
        metrics (str): A comma-separated list of metric keys to retrieve.

    Returns:
        dict: A dictionary containing the requested metrics and their values.
    """
    # Request parameters
    params = {"component": project_id, "metricKeys": metrics}

    # Make the request
    response = requests.get(METRICS_API, params=params, headers=sonarcloud_header())
    if response.status_code == 200:
        stats = response.json()["component"]["measures"]
    else:
        LOGGER.error(
            f"Failed to retrieve stats for project {project_id}: {response.text}"
        )
        stats = {}
    return stats


@click.group()
def cli():
    """CLI for managing SonarCloud projects.

    To use this CLI, ensure you have set the SONARCLOUD_TOKEN environment variable in your project `.env` file.
    """
    pass


@cli.command()
@click.argument("org", type=str, default="openmod-tracker")
@click.argument(
    "repo_list",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
)
def create(org: str, repo_list: Path):
    """Creates SonarCloud projects for the specified GitHub repositories.

    Newly created projects will need to be clicked on in the SonarCloud UI to complete the setup.

    ORG is the name of the SonarCloud (and GitHub) organization.

    REPO_LIST is the path to CSV file containing a 'repo' column with GitHub repository URLs.
    """
    repos = pd.read_csv(repo_list)
    for repo in tqdm(repos.repo.values, desc="Creating projects"):
        if not has_bindings(f"https://github.com/{org}/{repo}"):
            project_key = create_project(org, repo)
            click.echo(f"Created SonarCloud project for repo {repo}: {project_key}")
        else:
            click.echo(f"Repo {repo} already created in SonarCloud.")


@cli.command()
@click.argument("org", type=str, default="openmod-tracker")
@click.argument(
    "output_path",
    type=click.Path(exists=False, file_okay=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--metrics",
    type=str,
    default="sqale_rating,reliability_rating,security_rating,effort_to_reach_maintainability_rating_a,duplicated_lines_density,security_hotspots_to_review_status",
    show_default=True,
    help="Comma-separated list of SonarCloud metrics to retrieve. To view metric key options visit <https://sonarcloud.io/api/metrics/search>",
)
def get_stats(org: str, output_path: Path, metrics: str):
    """Retrieves SonarCloud project statistics.

    ORG is the name of the SonarCloud (and GitHub) organization.

    OUTPUT_PATH is the path to the output CSV file to save the retrieved project statistics.
    """
    repos = get_analysed_repo_keys(org)
    all_stats = []
    for repo, key in tqdm(repos.items(), total=len(repos), desc="Retrieving stats"):
        stats = get_project_stats(key, metrics)
        if not stats:
            click.echo(
                f"Failed to retrieve stats for project {repo}. "
                "Ensure you have triggered the initial analysis in the SonarCloud UI before attempting to retrieve stats."
            )
        else:
            all_stats.append(pd.DataFrame(stats).assign(repo=repo))
    if all_stats:
        pd.concat(all_stats).to_csv(output_path, index=False)
    else:
        click.echo("No valid stats retrieved.")


if __name__ == "__main__":
    cli()
