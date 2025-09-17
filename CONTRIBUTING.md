# Contributing guidelines

We're really glad you're reading this, because we rely on the community to help maintain this project.

Some of the resources to look at if you're interested in contributing:

- Look at open issues tagged with ["help wanted"](https://github.com/open-energy-transition/openmod-tracker/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) and ["good first issue"](https://github.com/open-energy-transition/openmod-tracker/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)

## Licensing

Copyright (C) Open Energy Transition (OET)
License: MIT / CC0 1.0

## Reporting bugs and requesting features

You can open an issue on GitHub to report bugs, request new openmod-tracker features, or to add/remove tools from the inventory.
Follow these links to submit your issue:

- [Report bugs or other problems while running openmod-tracker locally](https://github.com/open-energy-transition/openmod-tracker/issues/new?template=BUG-REPORT.yml).
  If reporting an error, please include a full traceback in your issue.

- [Request features that openmod-tracker does not already include](https://github.com/open-energy-transition/openmod-tracker/issues/new?template=FEATURE-REQUEST.yml).

- [Report missing or incorrectly included tools](https://github.com/open-energy-transition/openmod-tracker/issues/new?template=TOOLS.yml).

- [Any other issue](https://github.com/open-energy-transition/openmod-tracker/issues/new).

## Submitting changes

### Setting up for development

1. Clone this repository
1. Install [pixi](https://pixi.sh/latest/).
1. Install all project dependencies:
   ```sh
   pixi install
   ```

1. Install pre-commit:
   ```sh
   pixi run pre-commit install
   ```

See the project README for more details on running specific commands.

### Contributing changes

To contribute changes:

1. Fork the project on GitHub.
1. Create a feature branch to work on in your fork (`git checkout -b new-fix-or-feature`).
1. Generate new datasets and test serving the website with `pixi run serve`.
1. Commit your changes to the feature branch (you should have `pre-commit` installed to ensure your code is correctly formatted when you commit changes).
1. Push the branch to GitHub (`git push origin new-fix-or-feature`).
1. On GitHub, create a new [pull request](https://github.com/open-energy-transition/openmod-tracker/pull/new/main) from the feature branch to the `main` branch.

### Pull requests

Before submitting a pull request, check whether you have:

- Added your changes to `CHANGELOG.md`.
- Added or updated the README to reflect your changes.

When opening a pull request, please provide a clear summary of your changes!

### Commit messages

Please try to write clear commit messages. One-line messages are fine for small changes, but bigger changes should look like this:

```text
A brief summary of the commit (max 50 characters)

A paragraph or bullet-point list describing what changed and its impact,
covering as many lines as needed.
```

### Code conventions

Start reading our code and you'll get the hang of it.

We mostly follow the official [Style Guide for Python Code (PEP8)](https://www.python.org/dev/peps/pep-0008/).

We have chosen to use [`ruff`](https://beta.ruff.rs/docs/) for code formatting and linting.
When run from the root directory of this repo, `pyproject.toml` should ensure that formatting and linting fixes are in line with our custom preferences (e.g., 88 character maximum line length).
To make this a smooth experience, you should run `pre-commit install` after setting up your development environment.
If you prefer, you can also set up your IDE to run these two tools whenever you save your files, and to have `ruff` highlight erroneous code directly as you type.
Take a look at their documentation for more information on configuring this.

We require all new contributions to have docstrings for all modules, classes and methods.
When adding docstrings, we request you use the [Google docstring style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

## Attribution

The layout and content of this document is partially based on the [Calliope project's contribution guidelines](https://github.com/calliope-project/calliope/blob/main/CONTRIBUTING.md).
