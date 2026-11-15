"""Loads adventures/<id>/adventure.yaml and validates it. Adventures can come
from several folders (M7: this repo's tests and scenarios, then the private
dnd-adventures repo); for an id in more than one, the first folder wins, and a
folder that does not exist is skipped. An adventure folder may hold its own
stat blocks in creatures/<stat_block_id>.yaml, for monsters outside the SRD,
and a map.yaml with the book's player map image (after M7)."""

import struct
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from solo_dm.core.adventure.map_schema import AdventureMap
from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.ports import AdventureSourcePort
from solo_dm.core.state.models import CreatureStatBlock


class UnknownAdventure(ValueError):
    pass


@dataclass(frozen=True)
class PlayerMapFile:
    map: AdventureMap
    image: Path
    size: tuple[int, int]  # width, height in pixels


class YamlAdventureSource(AdventureSourcePort):
    def __init__(self, *roots: Path) -> None:
        self._roots = [r for r in roots if r.is_dir()]

    def available(self) -> list[str]:
        return sorted({str(p.parent.relative_to(root))
                       for root in self._roots for p in root.rglob("adventure.yaml")})

    def load(self, adventure_id: str) -> Adventure:
        path = self._folder(adventure_id) / "adventure.yaml"
        try:
            return Adventure.model_validate(yaml.safe_load(path.read_text()))
        except ValidationError as invalid:
            raise ValueError(f"{path}: {invalid}") from invalid

    def stat_blocks(self, adventure_id: str) -> dict[str, CreatureStatBlock]:
        """The adventure's own stat blocks, by id (none: an empty dict)."""
        folder = self._folder(adventure_id) / "creatures"
        blocks = [CreatureStatBlock.model_validate(yaml.safe_load(p.read_text()))
                  for p in sorted(folder.glob("*.yaml"))] if folder.is_dir() else []
        return {b.stat_block_id: b for b in blocks}

    def player_map(self, adventure_id: str) -> PlayerMapFile | None:
        """The adventure's map.yaml and player map image, if it has both. Takes
        the folder ("scenarios/player_map") or the adventure's own id, which is
        what a campaign stores."""
        folder = self._folder(adventure_id)
        path = folder / "map.yaml"
        if not path.is_file():
            return None
        adventure_map = AdventureMap.model_validate(yaml.safe_load(path.read_text()))
        if adventure_map.player_image is None:
            return None
        image = folder / adventure_map.player_image
        return PlayerMapFile(adventure_map, image, png_size(image))

    def _folder(self, adventure_id: str) -> Path:
        for root in self._roots:
            if (root / adventure_id / "adventure.yaml").is_file():
                return root / adventure_id
        for root in self._roots:
            for path in sorted(root.rglob("adventure.yaml")):
                if path.parent.name == adventure_id:
                    return path.parent
        raise UnknownAdventure(
            f"No adventure '{adventure_id}'. Adventures: {', '.join(self.available())}"
        )


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: the player map must be a PNG image")
    return struct.unpack(">II", header[16:24])
