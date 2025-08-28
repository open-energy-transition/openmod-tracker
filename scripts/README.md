# GitHub Repository Management Scripts

This directory contains scripts for managing GitHub repositories, including forking repositories and keeping them in sync with their upstream sources.

## Setup

### 1. Install Required Packages

```bash
pip install python-dotenv PyGithub
```

### 2. Environment Configuration

Create a `.env` file in the root directory of the project with the following variables:

```
GITHUB_TOKEN=github_personal_access_token
GITHUB_ORG=github_organization
```

If `GITHUB_ORG` is not specified, it will default to `openmod-tracker`.

#### GitHub Personal Access Token

You need a GitHub Personal Access Token with the `repo` scope to use these scripts:

1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Click "Generate new token"
3. Give it a name (e.g., "Repository Management Scripts")
4. Select the `repo` scope
5. Click "Generate token"
6. Copy the token and add it to your `.env` file

## Repository Data Source

Repositories to fork are read from a CSV file (`inventory/output/stats.csv`). The CSV file must contain an `html_url` column with GitHub repository URLs.

Example CSV format:
```csv
id,name,html_url,description,other_columns
1,repo1,https://github.com/original_owner/repo_name,Repository description,data
2,repo2,https://github.com/another_owner/another_repo,Another description,data
```

The script extracts the owner and repository name from the `html_url` column.

## Scripts

### Fork Repositories Script (`fork_repos.py`)

This script forks GitHub repositories to the specified organization and keeps existing forks in sync with their upstream repositories.

#### Usage

```bash
python scripts/fork_repos.py
```

The script will:
1. Read repository information from the CSV file
2. Check if each repository is already forked to organization
3. Fork repositories that haven't been forked yet
4. Sync existing forks with their upstream repositories
5. Log all operations to a file (`scripts/fork_results.log`)


## Logging

Log files are created in the `scripts` directory by default:
- `scripts/fork_results.log` for the forking script
