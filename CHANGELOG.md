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
