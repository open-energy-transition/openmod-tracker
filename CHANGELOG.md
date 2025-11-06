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
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- more bots to be excluded in dev metrics page.

### Changed

- Dev metrics timeseries defaults to non-cumulative.

### Fixed

- duplicate entries in interaction stats.
- fix github api method call on reaching rate limit.
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
