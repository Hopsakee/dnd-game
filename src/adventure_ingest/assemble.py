"""assemble: the stage files of an ingest folder into one adventure.yaml,
validated by the engine's schema (BUILD_PLAN M8). Exits are not written by any
skill: each opening in map.yaml is an exit, leading to the place that holds the
opening it meets, through a door when its kind is door."""

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
from solo_dm.core.adventure.map_schema import AdventureMap
from solo_dm.core.adventure.schema import Adventure


def assemble(folder: Path) -> list[str]:
    """Writes folder/adventure.yaml, or returns the problems and writes nothing."""
    try:
        stages = {name: load_stage(folder, name) for name in STAGES}
        adventure_map = AdventureMap.model_validate(load_yaml(folder / "map.yaml"))
    except FileNotFoundError as missing:
        return [f"{Path(missing.filename).name} is missing"]
    except ValidationError as invalid:
        return [f"{invalid.title}: {e['msg']} at {'.'.join(map(str, e['loc']))}"
                for e in invalid.errors()]
    data = build(adventure_map, **stages)
    try:
        Adventure.model_validate(data)
    except ValidationError as invalid:
        return [f"adventure.yaml: {e['msg'].removeprefix('Value error, ')}"
                for e in invalid.errors()]
    (folder / "adventure.yaml").write_text(
        "# Assembled by `adventure-ingest assemble` from the stage files next to it.\n"
        + yaml.safe_dump(data, sort_keys=False, width=88, allow_unicode=True))
    return []


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text())


def load_stage(folder: Path, name: str):
    file_name, model = STAGES[name]
    return model.model_validate(load_yaml(folder / file_name))


def build(adventure_map: AdventureMap, locations: LocationsStage, creatures: CreaturesStage,
          items: ItemsStage, challenges: ChallengesStage) -> dict:
    places = {**adventure_map.locations, **adventure_map.off_map}
    owner = {o.id: place_id for place_id, place in places.items() for o in place.openings}

    def without(model, *fields) -> dict:
        return model.model_dump(exclude_defaults=True, exclude=set(fields))

    def location(place) -> dict:
        openings = places[place.id].openings if place.id in places else ()
        exits = []
        for o in openings:
            exit_ = {"id": o.id, "to": owner.get(o.meets, o.meets), "direction": o.direction}
            if o.id in place.hidden_exits:
                exit_["hidden"] = {"dc": place.hidden_exits[o.id]}
            if o.kind == "door":
                exit_["door"] = True
            exits.append(exit_)
        data = {"id": place.id, "name": place.name, "description": place.description,
                "exits": exits, **without(place, "id", "name", "description", "hidden_exits")}
        for key, found in (("checks", challenges.challenges), ("hazards", items.hazards),
                           ("uses", items.uses)):
            here = [without(x, "at") for x in found if x.at == place.id]
            if here:
                data[key] = here
        return data

    entities = []
    for creature in creatures.creatures:
        data = without(creature)
        checks = [without(c, "at") for c in challenges.challenges if c.at == creature.id]
        if checks:
            data["checks"] = checks
        entities.append(data)
    adventure = {"id": locations.id, "title": locations.title,
                 "start_location": locations.start_location,
                 "win_condition": items.win_condition.model_dump()}
    if creatures.guardian is not None:
        adventure["guardian"] = creatures.guardian.model_dump()
    adventure["locations"] = [location(p) for p in locations.locations]
    adventure["entities"] = entities
    adventure["items"] = [without(i) for i in items.items]
    adventure["locks"] = [without(lock) for lock in items.locks]
    return adventure
