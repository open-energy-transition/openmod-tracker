
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

The model inventory and associated statistics can be updated by calling `pixi run get-stats`.
If nothing has changed in the source code files or CSVs, nothing will run.
To force an update, delete the CSVs in `inventory/output` and _then_ call `pixi run get-stats`.

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
If this is the case for your tool and you would like it to be included in this inventory then you should raise an issue on the appropriate [ecosyste.ms repository](https://github.com/ecosyste-ms).
