# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Data model for energy system modeling tool collection."""

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from data_model.tool import Tool


class ToolCollection(BaseModel):
    """Represent a collection of energy system modeling tools.

    Attributes:
    ----------
    tools : List[Tool]
        List of Tool objects.

    """

    tools: Annotated[list[Tool], Field(description="List of Tool objects.")]

    def __iter__(self) -> Iterator[Tool]:  # type: ignore
        """Return an iterator over the list of Tool objects.

        Returns:
        -------
        Iterator[Tool]
            An iterator over the Tool objects contained in the collection.

        """
        return iter(self.tools)

    def __len__(self) -> int:
        """Return the number of tools in this collection.

        Returns:
        -------
        int
            The number of Tool objects in the collection.

        """
        return len(self.tools)

    def to_csv(self, file_path: str | Path, format_type: str) -> None:
        """Write collection to CSV file using the specified format.

        Parameters
        ----------
        file_path : str | Path
            Path to the output CSV file.
        format_type : str
            The export format to use. Valid values: 'tools', 'filtered', 'stats',
            'scores', 'docs', 'package_downloads'.

        Raises:
        ------
        ValueError
            If format_type is not a valid export format.

        """
        if not self.tools:
            return

        # Map format type to the corresponding method name
        format_method_map = {
            "tools": "to_tools_csv_row",
            "filtered": "to_filtered_csv_row",
            "stats": "to_stats_csv_row",
            "scores": "to_scores_csv_row",
            "docs": "to_docs_csv_row",
            "package_downloads": "to_package_downloads_csv_row",
        }

        if format_type not in format_method_map:
            valid_formats = ", ".join(format_method_map.keys())
            raise ValueError(
                f"Invalid format_type '{format_type}'. "
                f"Valid options are: {valid_formats}"
            )

        # Get the method name and call it on each tool
        method_name = format_method_map[format_type]
        rows = [getattr(tool, method_name)() for tool in self.tools]

        # For package_downloads, collect all unique fieldnames (dynamic columns)
        if format_type == "package_downloads":
            fieldnames = []
            seen = set()
            for row in rows:
                for key in row.keys():
                    if key not in seen:
                        fieldnames.append(key)
                        seen.add(key)
        else:
            fieldnames = list(rows[0].keys())

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
