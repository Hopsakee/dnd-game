"""Loads adventures/<id>/adventure.yaml and validates it."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.ports import AdventureSourcePort


class UnknownAdventure(ValueError):
    pass


class YamlAdventureSource(AdventureSourcePort):
    def __init__(self, root: Path) -> None:
        self._root = root

    def available(self) -> list[str]:
        return sorted(str(p.parent.relative_to(self._root))
                      for p in self._root.rglob("adventure.yaml"))

    def load(self, adventure_id: str) -> Adventure:
        path = self._root / adventure_id / "adventure.yaml"
        if not path.is_file():
            raise UnknownAdventure(
                f"No adventure '{adventure_id}'. Adventures: {', '.join(self.available())}"
            )
        try:
            return Adventure.model_validate(yaml.safe_load(path.read_text()))
        except ValidationError as invalid:
            raise ValueError(f"{path}: {invalid}") from invalid
