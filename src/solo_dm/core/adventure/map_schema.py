"""map.yaml: the map read into named openings (the M8 map convention, Jelle
2026-11-14) and, for the player map (after M7), each location's cells on the
map's grid. Lives next to adventure.yaml; optional."""

from typing import Literal

from pydantic import Field, model_validator

from solo_dm.core.adventure.schema import AdventureModel

Cell = tuple[int, int, int, int]  # first column, first row, last column, last row


class Opening(AdventureModel):
    id: str
    kind: Literal["door", "archway", "junction", "outside"]
    direction: str
    at: tuple[int, int] | None = None  # pixel position on the map image
    meets: str


class MapLocation(AdventureModel):
    openings: tuple[Opening, ...] = ()
    features: tuple[str, ...] = ()  # the map's small letters in this location
    cells: tuple[Cell, ...] = ()  # rectangles of grid cells it covers


class AdventureMap(AdventureModel):
    image: str  # the map as printed for the DM, which the map step reads (M8)
    # The book's map for players: shown as the party explores (after M7).
    player_image: str | None = None
    cell_px: float | None = Field(default=None, gt=0)  # one grid cell, in image pixels
    locations: dict[str, MapLocation]
    off_map: dict[str, MapLocation] = {}

    @model_validator(mode="after")
    def _player_image_is_usable(self) -> "AdventureMap":
        for name in (self.image, self.player_image):
            if name is not None and ("/" in name or "\\" in name or name.startswith(".")):
                raise ValueError(f"'{name}' must be a file name next to map.yaml")
        if self.player_image is not None and self.cell_px is None:
            raise ValueError("a player_image needs cell_px, the size of one grid cell")
        return self
