
# Smarter Investments in Open Energy Planning: How Data Can Guide Decision-Makers

*Repository for analyzing the maturity and adoption of open-source Energy System Modelling (ESM) tools using Git data and other publicly available sources (e.g., ecosyste.ms and opensustain.tech). It is online at [Streamlit](https://open-esm-analysis.streamlit.app/).*

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
- Visualises ESM tool statistics using in a [Streamlit](https://streamlit.io/) application: <https://open-esm-analysis.streamlit.app/>

## Installation

1. Clone this repository
1. Install [pixi](https://pixi.sh/latest/).
1. Install all project dependencies:

   ```sh
   pixi install
   ```

## Serve app locally

To serve the streamlit app, call `pixi run serve` from the command line.

## Refreshing data

Data refreshes are necessary when changing the inventory source code and are recommended at periodic intervals to capture upstream changes.
These are automated with a Github action but you can force a manual update locally following the below steps.


>[!NOTE]
>The below steps leverage [pixi tasks](https://pixi.sh/dev/workspace/advanced_tasks/) which will run all steps in the sequence if there have been changes to the source code or it is the first time you are running the command.
>If you want to just run one step in isolation you will need to call the Python script directly, e.g. `pixi run python inventory/get-stats.py inventory/output/filtered.csv inventory/output/stats.csv`.
>See `pixi.toml` for the command to run for each step.

>[!WARNING]
>Data refreshes _override_ the entire dataset.
>This can be time consuming, particularly when refreshing [user statistics](#user-stats) which will take hours.

### Tool stats

The model inventory and associated statistics can be updated by calling `pixi run get-stats`.
This will get tools from the various upstream inventories, filter them based on [our requirements](#our-data-processing-approach), and then get stats from ecosyste.ms and by speculatively querying known documentation sites.

### User stats

The repository user interactions can be updated by calling `pixi run get-repo-users`.
This gets _all_ repository data from scratch as the [PyGitHub](https://github.com/PyGithub/PyGithub) API does not allow us to only access the most recent changes.
Therefore, it can be very time consuming.

The repository user details can be updated by calling `pixi run get-user-details`.
This will append `inventory/output/user_details.csv` with any new users listed in `inventory/output/user_interactions.csv`.
As we have already prepared the initial set of users, this should be relatively quick when refreshing.

### Our data processing approach

We collect tools listed in the following inventories:

- [LF Energy Landscape](https://github.com/lf-energy/lfenergy-landscape)
- [G-PST OpenTools](https://api.github.com/repos/G-PST/opentools)
- [Open Sustainable Technology](https://github.com/protontypes/open-sustainable-technology)
- [Open Energy Modelling Initiative](https://wiki.openmod-initiative.org/wiki/Open_Models)

Alongside a [pre-compiled list](./inventory/pre_compiled_esm_list.csv) of tools (based on [DOI:10.1016/j.rser.2018.11.020](https://doi.org/10.1016/j.rser.2018.11.020) and subsequent searches), we filter the collection to:

- Remove duplicates according to tool name, after normalising the string to lower case and converting all special characters to underscores.
- Remove duplicates according to tool source code URL, after normalising the string to lower case.
- Remove tools without a valid Git repository for their source code (hosted on e.g. GitHub, GitLab, Bitbucket, or a custom domain).
- Remove tools that we know, from manual inspection, are not appropriate for including in our inventory.
  This may be because they are duplicates of the same tool that we cannot catch with our simple detection methods, are supporting tools for another listed tool, or have been catalogued erroneously in the upstream inventory.
  We give the reason for manually excluding a tool in our [list of exclusions](./inventory/exclusions.csv).

For the remaining tools, we collect source code repository and package data using <https://ecosyste.ms> APIs.
At this stage, some tools will be filtered out for lack of any data or because they are written in a proprietary programming language (e.g. MATLAB, GAMS, AMPL).
Lack of repository data is usually because the repository is no longer available or because it is not publicly accessible (which we deem to be *not* an open source tool, irrespective of the tool's license).
In very rare cases (<1% of tools in the inventory), the repository host is not indexed by <https://ecosyste.ms>.
If this is the case for your tool and you would like it to be included in this inventory then you should open an issue on the appropriate [ecosyste.ms repository](https://github.com/ecosyste-ms).

Further to data from <https://ecosyste.ms>, we attempt to link repositories with their documentation sites.
The most likely hosts for documentation are readthedocs.org, Github/Gitlab Pages, or repository Wikis.
For each repository, we check the most likely URL for each of these as they follow a pre-defined structure.
If we get a positive match, we link that to the repository.
This is not perfect as sometimes a project uses an unexpected site URL for their documentation.
If your project is listed without documentation that you know exists then [open an issue](https://github.com/open-energy-transition/open-esm-analysis/issues/new)!
