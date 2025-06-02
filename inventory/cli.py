import re
from pathlib import Path

import click
import filter_tools
import get_stats
import get_tools
import pandas as pd


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

    automatic_entries = pd.concat(
        [
            get_tools.get_lf_energy_landscape(),
            get_tools.get_opensustaintech(),
            get_tools.get_g_pst_opentools(),
        ]
    )
    automatic_entries["url"] = automatic_entries["url"].str.strip("/").str.lower()

    manual_entries = get_tools.load_manual_list(automatic_entries["url"])
    entries = pd.concat([automatic_entries, manual_entries])
    entries["id"] = entries.name.map(
        lambda x: re.sub(r"\s|\-|\.", "_", str(x).strip().lower())
    )
    entries.to_csv(outfile, index=False)


@cli.command()
@click.argument("infile", type=click.Path(exists=True, dir_okay=False, file_okay=True))
@click.argument(
    "outfile", type=click.Path(exists=False, dir_okay=False, file_okay=True)
)
@click.option(
    "--ignore",
    type=click.Choice(get_tools.TOOL_TYPES),
    multiple=True,
    required=False,
    help="Ignore source of data as part of the filtering process.",
)
def filter_esm_list(infile: Path, outfile: Path, ignore: tuple[str]):
    """Filter collated tool list."""
    entries = pd.read_csv(infile)
    entries_ignore_sources = entries.where(~entries["source"].isin(ignore)).dropna(
        how="all"
    )
    filtered_entries = filter_tools.drop_duplicates(entries_ignore_sources, on="id")
    filtered_entries = filter_tools.drop_duplicates(entries_ignore_sources, on="url")
    filtered_entries = filter_tools.drop_no_git(filtered_entries)

    filtered_entries.to_csv(outfile, index=False)


@cli.command()
@click.argument("infile", type=click.Path(exists=True, dir_okay=False, file_okay=True))
@click.argument(
    "outfile", type=click.Path(exists=False, dir_okay=False, file_okay=True)
)
def get_ecosystems_data(infile: Path, outfile: Path):
    """Get ecosyste.ms stats for all entries."""
    entries = pd.read_csv(infile)
    stats_df = get_stats.get_ecosystems_entry_data(entries.url)
    stats_df.to_csv(outfile)


if __name__ == "__main__":
    cli()
