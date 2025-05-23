import re
from pathlib import Path

import click
import pandas as pd

from . import filter_tools, get_tools


@click.group()
def cli(args=None):
    """Console script for open-esm-analysis."""
    click.echo("Welcome to the OET Energy System Modelling (ESM) tool inventory.\n")
    return 0


@cli.command()
@click.argument(
    "outfile", type=click.Path(exists=False, dir_okay=False, file_okay=True)
)
def get_esm_list(outfile: Path):
    """Get latest ESM list from various sources."""

    entries = pd.concat(
        [
            get_tools.get_lf_energy_landscape(),
            get_tools.get_opensustaintech(),
            get_tools.get_g_pst_opentools(),
        ]
    )
    entries["id"] = entries.name.map(
        lambda x: re.sub(r"\s|\-|\.", "_", x.strip().lower())
    )
    entries.to_csv(outfile)


@cli.command()
@click.argument("infile", type=click.Path(exists=True, dir_okay=False, file_okay=True))
@cli.command()
@click.argument(
    "outfile", type=click.Path(exists=False, dir_okay=False, file_okay=True)
)
@click.option(
    "ignore_sources",
    type=click.Choice(get_tools.TOOL_TYPES),
    required=False,
    default=[],
)
def filter_esm_list(infile: Path, outfile: Path, ignore_sources: tuple[str]):
    """Validate entries against schema."""
    entries = pd.read_csv(infile, index_col="id")
    entries_ignore_sources = entries.where(
        ~entries["source"].isin(ignore_sources)
    ).dropna(how="all")
    filtered_entries = filter_tools.drop_duplicates(entries_ignore_sources)
    filtered_entries = filter_tools.drop_no_git(filtered_entries)

    filtered_entries.to_csv(outfile)


if __name__ == "__main__":
    cli()
