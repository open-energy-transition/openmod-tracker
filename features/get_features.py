# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Get features from the openmod-features repository."""

from pathlib import Path

import click


def clone_features_repo(repo_url: str, branch: str, clone_dir: Path):
    """Clone the features repository.

    Args:
        repo_url (str): URL of the repository to clone
        branch (str): Branch of the repository to clone
        clone_dir (Path): Directory to clone the repository into
    """
    pass


@click.command()
@click.argument(
    "features-host",
    type=str,
    default="https://github.com/open-energy-transition/openmod-features",
)
@click.argument(
    "outdir",
    type=click.Path(exists=False, dir_okay=True, file_okay=False, path_type=Path),
    default=Path(__file__).parent / "output",
)
@click.option("--branch", type=str, default="main")
def cli(features_host: str, outdir: Path, branch: str):
    """Get ecosyste.ms stats for all entries."""
    # TODO: Implement this with release tarballs from the openmod-features github
    clone_features_repo(features_host, branch, outdir)


if __name__ == "__main__":
    cli()
