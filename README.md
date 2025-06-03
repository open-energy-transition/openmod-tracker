
# Smarter Investments in Open Energy Planning: How Data Can Guide Decision-Makers

*Repository for analyzing Energy System Modelling (ESM) tools using Git data and other publicly available sources (e.g., ecosyste.ms and opensustain.tech). It is online at [Streamlit](https://open-esm-analysis.streamlit.app/).*

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
  - Issues
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
