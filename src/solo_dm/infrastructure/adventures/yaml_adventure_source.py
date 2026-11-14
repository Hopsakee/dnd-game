"""Loads adventures/<id>/adventure.yaml and validates it. Adventures can come
from several folders (M7: this repo's tests and scenarios, then the private
dnd-adventures repo); for an id in more than one, the first folder wins, and a
folder that does not exist is skipped. An adventure folder may hold its own
stat blocks in creatures/<stat_block_id>.yaml, for monsters outside the SRD."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.ports import AdventureSourcePort
from solo_dm.core.state.models import CreatureStatBlock


class UnknownAdventure(ValueError):
    pass


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

    def _folder(self, adventure_id: str) -> Path:
        for root in self._roots:
            if (root / adventure_id / "adventure.yaml").is_file():
                return root / adventure_id
        raise UnknownAdventure(
            f"No adventure '{adventure_id}'. Adventures: {', '.join(self.available())}"
        )
