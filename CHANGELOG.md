<!--
SPDX-FileCopyrightText: openmod-tracker contributors

SPDX-License-Identifier: MIT
-->

<!---
Changelog headings can be any of:

Added: for new features.
Changed: for changes in existing functionality.
Deprecated: for soon-to-be removed features.
Removed: for now removed features.
Fixed: for any bug fixes.
Security: in case of vulnerabilities.

Release headings should be of the form:
## YEAR-MONTH-DAY
-->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Calendar Versioning](https://calver.org/).

## 2026-08-31

### Fixed
- Fix failing CI

## 2026-07-31

### Fixed

- Failing dashboard user interaction page due to NaNs in user details (#252).
- Rely on existing tool CSV as a fallback of all tools, in case one of the upstream inventories becomes unavailable.
- Extend use of existing tools stats as fallback on all non-404 response codes when querying ecosyste-ms API (previously only 500 status code).
- Circumvent new readthedocs SSL error on certain domain name getters.

### Added

- `assetra` to pre-compiled list (#250).
- Add the `get_download_data.py` script to process package downloads and a dedicated visualisation page in the dashboard (#125).

### Changed

- Remove mescal & sms++ with active exclusions (reasons given in `inventory/exclusions.csv`).

## 2026-05-28

### Added

- Test docker image in CI

### Fixed

- Delete github pagination cache to get a correct representation of repo interactions
- Drop duplicates in repo interactions CSV
- Ensure duplicates are removed from repo interactions

## Changed

- Updated development page bot regex
- Start scorecard page on empty
- Move score further left in main dashboard table

## 2026-05-27

### Added

- Active maintainer number (#182).
- Repo dependabot, code quality, and secret scanning in `openmod-tracker` source code repo.
- Automated release process following monthly inventory auto-update.
- Add the `get_scores.py` script to process the OpenSSF scores and a dedicated visualisation page in the dashboard (#217).
- Return the ISO3 country code in `user_classifications.csv` instead of the country name (#96).

### Fixed

- Failing duplicated URL filtering when ecosyste.ms server is down.

## Changed

- Tulipa energy & antares_simulator categories updated

## 2026-03-12

### Added

- Repo interaction and user detail cleaning when removing a repo with existing downloaded data.
- Warning on category assignments referring to IDs not defined in the tool list.
- Active maintainer number.

### Fixed

- Anaconda data downloader when entering a new year.
- Source code URL redirects (identified when `NREL` org changed to `NatLabRockies` across multiple repos).
- RTD link checks when too many requests are made.

## Changed

- Some existing tools added to exclusions following refreshed review.
- host and repo name combined in user analysis.
  We now store data in the form `<host>:<repo>` where host is one of `gh` (GitHub) or `gl` (Gitlab).
- Project naming convention, to choose the closest name to the repository name.
- IDs used in category assignment to match updated IDs.

## 2025-11-06

### Added

- more bots to be excluded in dev metrics page.

### Changed

- Dev metrics timeseries defaults to non-cumulative.
- Automated stats updater to run once a month and to include user data updates as well.

### Fixed

- duplicate entries in interaction stats.
- github api method call on reaching rate limit.
- ungraceful response to empty (NoneType) descriptions and readmes in user data.
- ensure commits are included in dashboard dev metrics.
- timeseries metric calculation when unselected timeseries data is needed.

### Removed

- "contributors" getter (we get all commits directly)

## 2025-11-04

### Changed

- Timeseries data from lines to bars & using gradient colour palette.
- 6-month interactions in main table from cumulative to absolute.

### Added

- Dashboard app smoke tests (incl. memory peak checks).
- Dashboard processing method unit tests.

### Fixed

- High peak memory consumption on loading dashboard.
- Incorrect % PRs reviewed calculation in dev metrics dashboard page.

## 2025-10-31

### Changed

- Clarify `language` column in tooltip (#141).

### Added

- **REVERTED - data quality is too low** Code quality metrics in dashboard (reliability, security, maintainability) (#63).
- Non-github project cloning to use in sonarcloud project analysis workflow.
- `Project Development Metrics` deep-dive page (#113).
- Disclaimer about our relationship with the Open Energy Modelling Initiative (openmod-initiative) (#143).

### Fixed

- Go direct to source to get Julia package download statistics (since `juliapkgstats` webpage has been periodically down).
- Repository forking/syncing scripts and sonarcloud project creator when used in anger.
- a bug in the "Updated" field. It now correctly reports the date-time of the most recent change to a tool's repository. However, this change can be a push to any branch, not just the main or published branch (#116).

## 2025-09-23

### Added

- Repository forking/upstream syncing scripts to maintain forks of all tracked tools within the `openmod-tracker` organisation (#80).

### Changed

- Dashboard text to improve SEO header and body text.

## 2025-09-18

### Added

- SonarCloud project creator and analysed project stats getter (#81).
- License specific to generated data + `reuse` to manage per-file licensing (#92).
- OET logo and license information in deployed dashboard.

### Fixed

- Country map in user interaction analysis missing all data (#94).
- Package download data shown as zero when it should be empty.
- Tools shown as having an associated package due to erroneous reference to a "Go" package that should only exist for tools written in Go.

### Changed

- Updated exclusion list to remove newly added `project-origin` & `mapyourgrid` as they aren't ESM tools.
- Tool score column is optional and toggled _off_ by default.
- Rebrand project: `open-esm-analysis` -> `openmod-tracker`.
- Added banner text in deployed dashboard to clarify that this is still a work in progress (#93).

## 2025-08-27

Initial release.

### Added

- Open Energy Modelling Tool inventory collector and stats getters.
- Tool user interaction data collector and user classification.
- Streamlit web dashboard.
- Docker image and cloudbuild config to deploy dashboard on Google Cloud Platform.
