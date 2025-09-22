<!--
SPDX-FileCopyrightText: openmod-tracker contributors

SPDX-License-Identifier: MIT
-->

# Open Energy Modelling Tool Tracker (openmod-tracker)

[![REUSE status](https://api.reuse.software/badge/github.com/open-energy-transition/openmod-tracker/)](https://api.reuse.software/info/github.com/open-energy-transition/openmod-tracker/)

Repository for analyzing the maturity and adoption of open-source Energy System Modelling (ESM) tools using Git and other publicly available data.
The result of the analysis is available in an [online dashboard](https://openmod-tracker.org/).

## Features

- Merges and filters ESM tools from various inventories:
  - [LF Energy Landscape](https://github.com/lf-energy/lfenergy-landscape)
  - [G-PST OpenTools](https://api.github.com/repos/G-PST/opentools)
  - [Open Sustainable Technology](https://github.com/protontypes/open-sustainable-technology)
  - [Open Energy Modelling Initiative](https://wiki.openmod-initiative.org/wiki/Open_Models)
- Fetches source code repository and package statistics for each tool via the [ecosyste.ms](https://ecosyste.ms) API:
  - Repository creation
  - Repository last change
  - Stars and Forks
  - Number of contributors
  - Dependent repositories
  - Downloads
  - development distribution score (DDS)
- Fetches repository interactions and interacting user data using the [GitHub REST API](https://docs.github.com/en/rest) and classifies users based on string matching.
- Visualises ESM tool statistics in a [Streamlit](https://streamlit.io/)-powered dashboard: <https://openmod-tracker.org/>

## Installation

1. Clone this repository
1. Install [pixi](https://pixi.sh/latest/).
1. Install all project dependencies:

   ```sh
   pixi install
   ```

## Serve app locally

To serve the streamlit app, call `pixi run -e app serve` from the command line.

## Test

You can run our minimal test suite by calling `pixi run test`.

## Troubleshooting

If the [development version dashboard](https://openmod-tracker.streamlit.app/) is not loading then you can try a few things:

1. Delete the site data for <https://openmod-tracker.streamlit.app> in your browser and refresh the page.
1. Clone this repository locally and run `pixi run test` from the terminal (having followed our [installation instructions](#installation)).
1. If the tests fail, you can debug by setting [traces/breakpoints](https://docs.python.org/3/library/pdb.html) in the app python scripts (`website/**/*.py`) and then run `pixi run -e app serve` in the terminal.
1. If the tests pass and you are a repository maintainer, you can reboot the app from [the streamlit dashboard](https://share.streamlit.io/).

## Refreshing data

Data refreshes are necessary when changing the inventory source code and are recommended at periodic intervals to capture upstream changes.
These are automated with a Github action but you can force a manual update locally following the steps below.

>[!NOTE]
>The below steps leverage [pixi tasks](https://pixi.sh/dev/workspace/advanced_tasks/) which will run all steps in the sequence if there have been changes to the source code or it is the first time you are running the command.
>If you want to just run one step in isolation you will need to call the Python script directly, e.g. `pixi run python inventory/get-stats.py inventory/output/filtered.csv inventory/output/stats.csv`.
>[User statistics](#user-stats) runs will require extra dependencies provided by the "geo" environment, e.g. `pixi run -e geo python user_analysis/classify_users.py`.
>See `pixi.toml` for the command to run for each step.

>[!WARNING]
>Data refreshes _override_ the entire dataset.
>This can be time consuming, particularly when refreshing [user statistics](#user-stats) which will take hours.

### Tool stats

The model inventory and associated statistics can be updated by calling `pixi run get-stats`.
This will get tools from the various upstream inventories, filter them based on [our requirements](#our-data-processing-approach), and then get stats from ecosyste.ms and by speculatively querying known documentation sites.

### User stats

All user statistics can be updated by calling `pixi run classify-users`.
However, some steps are quite time consuming, so you may prefer to explicitly run them in turn.

The repository user interactions can be updated by calling `pixi run get-repo-users`.
This gets _all_ repository data from scratch as the [PyGitHub](https://github.com/PyGithub/PyGithub) API does not allow us to only access the most recent changes.
Therefore, it can be very time consuming.

The repository user details can be updated by calling `pixi run get-user-details`.
It will run `get-repo-users` first if this hasn't already been run.
This will append `inventory/output/user_details.csv` with any new users listed in `inventory/output/user_interactions.csv`.
As we have already prepared the initial set of users, this should be relatively quick when refreshing.

Finally, our heuristic user classification approach can be applied to the updated user details by calling `pixi run classify-users`.

### Code quality assessment

We manage forks of all GitHub repositories within our own GitHub organisation in order to have the necessary permissions to undertake code quality assessments.

#### Forking Repositories

The `code_quality/fork_repos.py` script forks GitHub repositories to the specified organization and keeps existing forks in sync with their upstream repositories.
An appropriate GitHub token for the organisation, with write access, must be provided at runtime.

The script will:

1. Read repository information from the CSV file (which must contain an `html_url` column with GitHub repository URLs)
2. Check if each repository is already forked to the organization
3. Fork repositories that haven't been forked yet
4. Sync existing forks with their upstream repositories
5. Log all operations to the specified log file

#### Running code quality assessment

The `code_quality/sonarcloud.py create` method will create SonarQube cloud platform projects for each of the forked repositories.
The `code_quality/sonarcloud.py get-stats` method will access the code quality statistics for all existing SonarQube cloud platform projects.

### Our data processing approach

We collect tools listed in the following inventories:

- [LF Energy Landscape](https://github.com/lf-energy/lfenergy-landscape)
- [G-PST OpenTools](https://api.github.com/repos/G-PST/opentools)
- [Open Sustainable Technology](https://github.com/protontypes/open-sustainable-technology)
- [Open Energy Modelling Initiative](https://wiki.openmod-initiative.org/wiki/Open_Models)

Alongside a [pre-compiled list](https://github.com/open-energy-transition/openmod-tracker/blob/main/inventory/pre_compiled_esm_list.csv) of tools (based on [DOI:10.1016/j.rser.2018.11.020](https://doi.org/10.1016/j.rser.2018.11.020) and subsequent searches), we filter the collection to:

- Remove duplicates according to tool name, after normalising the string to lower case and converting all special characters to underscores.
- Remove duplicates according to tool source code URL, after normalising the string to lower case.
- Remove tools without a valid Git repository for their source code (hosted on e.g. GitHub, GitLab, Bitbucket, or a custom domain).
- Remove tools that we know, from manual inspection, are not appropriate for including in our inventory.
  This may be because they are duplicates of the same tool that we cannot catch with our simple detection methods, are supporting tools for another listed tool, or have been catalogued erroneously in the upstream inventory.
  We give the reason for manually excluding a tool in our [list of exclusions](https://github.com/open-energy-transition/openmod-tracker/blob/main/inventory/exclusions.csv).

For the remaining tools, we collect source code repository and package data using <https://ecosyste.ms> APIs.
At this stage, some tools will be filtered out for lack of any data.
Lack of repository data is usually because the repository is no longer available or because it is not publicly accessible (which we deem to be _not_ an open source tool, irrespective of the tool's license).
In very rare cases (<1% of tools in the inventory), the repository host is not indexed by <https://ecosyste.ms>.
If this is the case for your tool and you would like it to be included in this inventory then you should open an issue on the appropriate [ecosyste.ms repository](https://github.com/ecosyste-ms).

Further to data from <https://ecosyste.ms>, we rely on other sources to (1) link repositories with their documentation sites, (2) Fill gaps in package download numbers, and (3) gather data on user interactions.

1. The most likely hosts for documentation are readthedocs.org, Github/Gitlab Pages, or repository Wikis.
   For each repository, we check the most likely URL for each of these as they follow a pre-defined structure.
   If we get a positive match, we link that to the repository.
   This is not perfect as sometimes a project uses an unexpected site URL for their documentation.
1. Most packages are indexed on PyPI, conda-forge or on public Julia package servers.
   For each of these, since <https://ecosyste.ms> data is often missing here, we use direct or third party APIs to query the downloads for the previous month.
1. User interaction data utilises the direct GitHub API.
   This is the API with which much of the <https://ecosyste.ms> database is generated.
   However, they don't store user data unless a user is also a repository owner.
   Direct use of the GitHub API is time intensive due to hourly request limits.
   Therefore, this data (e.g. informing the rate of user interactions over the past 6 months) is updated less frequently than other tools stats.

## Release guideline

We follow calendar versioning (CalVer) in this project.
To deploy new versions of the dashboard to <https://openmod-tracker.org>, follow these steps:

- Update the changelog with changes since the previous release under a heading with the current date in `YYYY-MM-DD` format.
- Update the version in the `pixi.toml` to the current date.
- Open a Pull Request with this change.
- Once status checks pass and the PR is approved and merged, create a tag locally on the latest commit in the main branch with the same name as the changelog heading, e.g.:

  ```sh
  git checkout main
  git pull
  git tag -a 2025-09-01
  git push --tag
  ```

- Create a release in the GitHub web console linked to the tag with the title `Release YYYY-MM-DD` and list the changes since the previous release.

## License

This project uses [REUSE](https://reuse.software/) to manage its licensing.

For a list of all `openmod-tracker contributors`, see [AUTHORS.md](AUTHORS.md).

The software in this repository is licensed under the [MIT license](LICENSES/MIT.txt).
The generated output data (`inventory/output/*`, `user_analysis/output/*`) are licensed under the [Creative Commons Attribution 4.0 license](LICENSES/CC-BY-4.0.txt) for easier reuse.
Individual configuration or generic files may be licensed [CC0 1.0 Universal](LICENSES/CC0-1.0.txt) and [Creative Commons Attribution ShareAlike 4.0](LICENSES/CC-BY-SA-4.0.txt); these files are marked explicitly either in the file header or in the [REUSE.toml](REUSE.toml) file.
