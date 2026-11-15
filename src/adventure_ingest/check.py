"""check <stage>: one stage file validated on its own, so a mistake is caught
in the step that made it (BUILD_PLAN M8)."""

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from adventure_ingest.stages import (
    STAGES,
    ChallengesStage,
    CreaturesStage,
    ItemsStage,
    LocationsStage,
)
from adventure_ingest.stat_blocks import find_stat_block
from solo_dm.core.adventure.map_schema import AdventureMap, MapLocation

REPO = Path(__file__).resolve().parents[2]


def check(stage: str, folder: Path, srd: Path = REPO / "srd") -> list[str]:
    if stage == "map":
        return check_map(folder)
    file_name, model = STAGES[stage]
    try:
        found = model.model_validate(yaml.safe_load((folder / file_name).read_text()))
    except FileNotFoundError:
        return [f"{file_name} is missing"]
    except ValidationError as invalid:
        return schema_problems(file_name, invalid)
    known = Known.of(folder)
    return {"locations": check_locations, "creatures": check_creatures,
            "items": check_items, "challenges": check_challenges}[stage](found, known, srd)


@dataclass(frozen=True)
class Known:
    """What the earlier stages decided: the places and openings on the map, and
    the creatures."""

    folder: Path
    openings: dict[str, set[str]]  # place id -> its opening ids
    creatures: set[str]

    @classmethod
    def of(cls, folder: Path) -> "Known":
        openings: dict[str, set[str]] = {}
        if (folder / "map.yaml").is_file():
            adventure_map = AdventureMap.model_validate(
                yaml.safe_load((folder / "map.yaml").read_text()))
            places = {**adventure_map.locations, **adventure_map.off_map}
            openings = {i: {o.id for o in p.openings} for i, p in places.items()}
        creatures: set[str] = set()
        if (folder / "creatures.yaml").is_file():
            creatures = {c.id for c in CreaturesStage.model_validate(
                yaml.safe_load((folder / "creatures.yaml").read_text())).creatures}
        return cls(folder, openings, creatures)

    @property
    def all_openings(self) -> set[str]:
        return set().union(*self.openings.values())


def check_locations(stage: LocationsStage, known: Known, srd: Path) -> list[str]:
    written = {p.id for p in stage.locations}
    problems = [f"'{i}' is on the map but has no name or description"
                for i in known.openings if i not in written]
    problems += [f"'{i}' is no place on the map" for i in written if i not in known.openings]
    if stage.start_location not in written:
        problems.append(f"start_location '{stage.start_location}' is no place")
    problems += [f"hidden exit '{e}' is no opening of '{p.id}'" for p in stage.locations
                 for e in p.hidden_exits if e not in known.openings.get(p.id, set())]
    return problems


def check_creatures(stage: CreaturesStage, known: Known, srd: Path) -> list[str]:
    problems = [f"'{c.id}' is in '{c.location}', which is no place"
                for c in stage.creatures if c.location not in known.openings]
    for c in stage.creatures:
        if find_stat_block(c.srd_ref, known.folder, srd) is None:
            problems.append(f"'{c.id}' has no stat block '{c.srd_ref}' in the SRD or creatures/")
    return problems


def check_items(stage: ItemsStage, known: Known, srd: Path) -> list[str]:
    items = {i.id for i in stage.items}
    problems = []
    for item in stage.items:
        if item.location is not None and item.location not in known.openings:
            problems.append(f"'{item.id}' is in '{item.location}', which is no place")
        if item.carried_by not in (None, "party", *known.creatures):
            problems.append(f"'{item.id}' is carried by '{item.carried_by}', who is no creature")
    for lock in stage.locks:
        if lock.exit not in known.all_openings:
            problems.append(f"lock on '{lock.exit}', which is no opening")
        if lock.key is not None and lock.key not in items:
            problems.append(f"the key of '{lock.exit}', '{lock.key}', is no item")
    problems += [f"'{x.at}' is no place" for x in (*stage.hazards, *stage.uses)
                 if x.at not in known.openings]
    problems += [f"a use at '{u.at}' takes '{u.item}', which is no item"
                 for u in stage.uses if u.item is not None and u.item not in items]
    return problems


def check_challenges(stage: ChallengesStage, known: Known, srd: Path) -> list[str]:
    targets = set(known.openings) | known.creatures
    return [f"challenge '{c.id}' is at '{c.at}', which is no place or creature"
            for c in stage.challenges if c.at not in targets]


def check_map(folder: Path) -> list[str]:
    try:
        adventure_map = AdventureMap.model_validate(
            yaml.safe_load((folder / "map.yaml").read_text()))
    except ValidationError as invalid:
        return schema_problems("map.yaml", invalid)
    places = {**adventure_map.locations, **adventure_map.off_map}
    openings = {o.id: o for place in places.values() for o in place.openings}
    problems = []
    for o in openings.values():
        partner = openings.get(o.meets)
        if partner is None:
            problems.append(f"'{o.id}' meets '{o.meets}', which is no opening")
        elif partner.meets != o.id:
            problems.append(f"'{o.id}' meets '{partner.id}', but '{partner.id}' "
                            f"meets '{partner.meets}'")
        elif partner.kind != o.kind:
            problems.append(f"'{o.id}' is {article(o.kind)} but its partner "
                            f"'{partner.id}' is {article(partner.kind)}")
        elif o.at is not None and partner.at is not None and o.at != partner.at:
            problems.append(f"'{o.id}' is at {list(o.at)} but its partner "
                            f"'{partner.id}' at {list(partner.at)}")
    for place_id, place in places.items():
        problems += naming_problems(place_id, place, place_id in adventure_map.off_map)
    problems += overlapping_cells(adventure_map)
    return problems


def naming_problems(place_id: str, place: MapLocation, off_map: bool) -> list[str]:
    """Openings are named after their place (room5 -> 5a, c3 -> c3a, village ->
    village_a) and lettered a, b, c, ... in the order listed; directions are
    unique within a place."""
    prefix = place_id + "_" if off_map else place_id.removeprefix("room")
    problems = [f"'{o.id}' is in '{place_id}', so its name starts with '{prefix}'"
                for o in place.openings
                if not (o.id.startswith(prefix) and len(o.id) == len(prefix) + 1)]
    if problems:
        return problems
    names = [o.id for o in place.openings]
    expected = [prefix + chr(ord("a") + i) for i in range(len(names))]
    if names != expected:
        problems.append(f"the openings of '{place_id}' are lettered {', '.join(names)}; "
                        f"expected {', '.join(expected)}")
    by_direction: dict[str, list[str]] = {}
    for o in place.openings:
        by_direction.setdefault(o.direction, []).append(o.id)
    problems += [f"'{place_id}' has two openings to the {d}: {', '.join(ids)}"
                 for d, ids in by_direction.items() if len(ids) > 1]
    return problems


def overlapping_cells(adventure_map: AdventureMap) -> list[str]:
    """Every floor cell belongs to exactly one location (the player map)."""
    owner: dict[tuple[int, int], str] = {}
    problems = []
    for place_id, place in adventure_map.locations.items():
        for c0, r0, c1, r1 in place.cells:
            for cell in ((c, r) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)):
                if cell in owner and owner[cell] != place_id:
                    problems.append(f"cell {list(cell)} belongs to both '{owner[cell]}' "
                                    f"and '{place_id}'")
                owner[cell] = place_id
    return problems


def article(kind: str) -> str:
    return f"an {kind}" if kind[0] in "aeiou" else f"a {kind}"


def schema_problems(name: str, invalid: ValidationError) -> list[str]:
    return [f"{name}: {e['msg']} at {'.'.join(map(str, e['loc']))}" for e in invalid.errors()]

