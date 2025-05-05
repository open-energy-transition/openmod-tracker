
# Smarter Investments in Open Energy Planning: How Data Can Guide Decision-Makers

*Repository for analyzing Energy System Modelling (ESM) tools using Git data and other publicly available sources (e.g., ecosyste.ms and opensustain.tech). It is online at [Streamlit](https://open-esm-analysis.streamlit.app/).*

## Features
- Fetches GitHub information via an API from ecosyste.ms
- Colects maturiy and activity scores from GitHub, e.g.,
  - Repository creation
  - Repository last change
  - Stars and Forks
  - Number of contributors
  - Dependent repositories
  - Downloads
  - Issues
- Calculates the development distribution score (DDS)

## Requirements
- Python 3.8+
- no GitHub API token required as data from ecosyste.ms are taken

## Installation
1. Clone this repository
2. Create a virtual environment:
   ```
   conda create --name open-esm-analysis
   ```
3. Activate virtual environment:
   ```
   conda activate open-esm-analysis
   ```
4. Install dpendencies
   ```
   pip install streamlit pandas itables datetime request
   ```
   or create a requirements.txt file with these packages and run:
   ```
   pip install -r requirements.txt
   ```

## Architecture
This application is showing selected data from already collected data from [ecosyste.ms](https://ecosyste.ms) via [Streamlit](https://open-esm-analysis.streamlit.app/).

## Refreshing Data
No updates are required as [ecosyste.ms](https://ecosyste.ms) is updating their data once a day.
