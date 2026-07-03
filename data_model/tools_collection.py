# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Data model for energy system modeling tool collection."""

from typing import Annotated
from pydantic import BaseModel, Field

from data_model.tool import Tool


class ToolsCollection(BaseModel):
    """
    Represent a collection of energy system modeling tools.

    Attributes
    ----------
    tools : List[Tool]
        List of Tool objects.

    """

    tools: Annotated[
        list[Tool], Field(description="List of Tool objects.")
    ]

    def __iter__(self) -> Iterator[Tool]:  # type: ignore
        """
        Return an iterator over the list of Tool objects.

        Returns
        -------
        Iterator[Tool]
            An iterator over the Tool objects contained in the collection.

        """
        return iter(self.tools)

    def __len__(self) -> int:
        """
        Return the number of tools in this collection.

        Returns
        -------
        int
            The number of Tool objects in the technologies list.

        """
        return len(self.tools)
