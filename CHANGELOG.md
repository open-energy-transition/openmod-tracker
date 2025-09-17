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

- SonarCloud project creator and analysed project stats getter (#81).

### Fixed

- Country map in user interaction analysis missing all data (#94).

### Changed

- Updated exclusion list to remove newly added `project-origin`, as it isn't an ESM tool.
- Tool score column is optional and toggled _off_ by default.
- Rebrand project: `open-esm-analysis` -> `openmod-tracker`.

## 2025-08-27

Initial release.

### Added

- Open Energy Modelling Tool inventory collector and stats getters.
- Tool user interaction data collector and user classification.
- Streamlit web dashboard.
- Docker image and cloudbuild config to deploy dashboard on Google Cloud Platform.
