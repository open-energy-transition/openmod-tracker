# GitHub Repository Management Scripts


## Setup

### 1. Install Required Packages

```bash
pip install requests pyyaml
```

### 2. GitHub Personal Access Token

You need a GitHub Personal Access Token with the `repo` scope to use these scripts:

1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Click "Generate new token"
3. Give it a name (e.g., "Repo Forking Script")
4. Select the `repo` scope
5. Click "Generate token"
6. Copy the token (you'll only see it once)

You can provide this token in one of two ways:
- Set it as an environment variable: `export GITHUB_TOKEN=your_token_here`
- Pass it directly to the scripts with the `-t` option

### 3. Configure Target Organization

You need to specify which GitHub organization will own the forked repositories:
- Set it as an environment variable: `export GITHUB_ORG=your_org_name`
- Pass it directly to the scripts with the `-o` option

## Scripts

### fork_repos.py

This script forks GitHub repositories specified in a YAML file into your organization.

#### Usage

```bash
python fork_repos.py -t YOUR_GITHUB_TOKEN -o YOUR_ORG [-f repos_file.yaml] [-l log_file.log]
```

#### Options

- `-t, --token`: GitHub Personal Access Token (required if not set as GITHUB_TOKEN environment variable)
- `-o, --org`: Target GitHub organization name (required if not set as GITHUB_ORG environment variable)
- `-f, --file`: YAML file containing repositories to fork (default: repos_to_fork.yaml)
- `-l, --log`: Log file path (default: fork_results.log)

#### Example

```bash
python fork_repos.py -o open-energy-transition
```

### sync_forks.py

This script synchronizes existing forks in your organization with their upstream repositories.

#### Usage

```bash
python sync_forks.py -t YOUR_GITHUB_TOKEN -o YOUR_ORG [-f repos_file.yaml] [-l log_file.log] [--dry-run]
```

#### Options

- `-t, --token`: GitHub Personal Access Token (required if not set as GITHUB_TOKEN environment variable)
- `-o, --org`: GitHub organization name that contains the forks (required if not set as GITHUB_ORG environment variable)
- `-f, --file`: YAML file containing repositories to check (default: repos_to_fork.yaml)
- `-l, --log`: Log file path (default: sync_results.log)

## Repository Configuration

Repositories to fork are specified in a YAML file (default: `repos_to_fork.yaml`) with the following format:

```yaml
repositories:
  - owner: original_owner
    name: repo_name
    description: Optional description

  - owner: another_owner
    name: another_repo
    description: Another optional description
```

The `owner` and `name` fields are required, while `description` is optional.

## Examples

### Setting Environment Variables (recommended)

```bash
# Set up environment variables
export GITHUB_TOKEN=your_token_here
export GITHUB_ORG=your_organization

# Fork repositories
python fork_repos.py

# Sync forks
python sync_forks.py
```

### Using Command-Line Options

```bash
# Fork repositories
python fork_repos.py -t your_token_here -o your_organization

# Sync forks
python sync_forks.py -t your_token_here -o your_organization
```
