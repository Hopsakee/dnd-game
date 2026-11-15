"""verify, the hard gate (BUILD_PLAN M8): an adventure folder the converter is
not done with until this returns no problems."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from adventure_ingest.stat_blocks import find_stat_block
from solo_dm.core.adventure.map_schema import AdventureMap
from solo_dm.core.adventure.schema import Adventure, Lock
from solo_dm.core.state.models import CreatureStatBlock


def verify(folder: Path, srd: Path) -> list[str]:
    try:
        adventure = Adventure.model_validate(
            yaml.safe_load((folder / "adventure.yaml").read_text()))
    except ValidationError as invalid:
        return [f"adventure.yaml: {e['msg']} at {'.'.join(map(str, e['loc']))}"
                for e in invalid.errors()]
    reached = explore(adventure)
    problems = [f"'{loc.id}' cannot be reached from '{adventure.start_location}'"
                for loc in adventure.locations if loc.id not in reached.locations]
    if adventure.win_condition.flag not in reached.flags:
        problems.append(f"win flag '{adventure.win_condition.flag}' cannot be set")
    problems += keys_behind_their_locks(adventure)
    problems += one_sided_locks(adventure)
    problems += missing_stat_blocks(adventure, folder, srd)
    problems += out_of_reach(adventure)
    if (folder / "map.yaml").is_file():
        problems += disagreements_with_the_map(adventure, load_map(folder / "map.yaml"))
    return problems


def load_map(path: Path) -> AdventureMap:
    return AdventureMap.model_validate(yaml.safe_load(path.read_text()))


def disagreements_with_the_map(adventure: Adventure, adventure_map: AdventureMap) -> list[str]:
    """Exits are the map's openings: same id, same door, leading where the
    opening's partner lies (the map convention, BUILD_PLAN M8)."""
    places = {**adventure_map.locations, **adventure_map.off_map}
    owner = {o.id: place_id for place_id, place in places.items() for o in place.openings}
    problems = []
    for loc in adventure.locations:
        openings = {o.id: o for o in places[loc.id].openings} if loc.id in places else {}
        exits = {e.id: e for e in loc.exits}
        problems += [f"opening '{i}' on the map is no exit of '{loc.id}'"
                     for i in openings if i not in exits]
        for exit_ in loc.exits:
            opening = openings.get(exit_.id)
            if opening is None:
                problems.append(f"exit '{exit_.id}' of '{loc.id}' is no opening on the map")
                continue
            if exit_.door != (opening.kind == "door"):
                problems.append(f"exit '{exit_.id}' is a door "
                                + ("in adventure.yaml but not on the map" if exit_.door
                                   else "on the map but not in adventure.yaml"))
            if owner.get(opening.meets) != exit_.to:
                problems.append(f"exit '{exit_.id}' leads to '{exit_.to}', but on the map it "
                                f"meets '{opening.meets}' in '{owner.get(opening.meets)}'")
    return problems


# A natural 20 plus the best level-1 modifier (+3, a 16 in the standard array)
# and proficiency (+2).
BEST_ROLL = 25


def out_of_reach(adventure: Adventure) -> list[str]:
    """Every obstacle can be passed by a level-1 hero's own rolls."""
    tasks = [(lock.exit, lock.force_dc, "force") for lock in adventure.locks]
    tasks += [(lock.exit, lock.pick_dc, "pick") for lock in adventure.locks]
    tasks += [(c.id, c.dc, "succeed")
              for placed in (*adventure.locations, *adventure.entities) for c in placed.checks]
    return [f"'{name}' needs DC {dc} to {verb}; a level-1 hero rolls {BEST_ROLL} at most"
            for name, dc, verb in tasks if dc is not None and dc > BEST_ROLL]


def missing_stat_blocks(adventure: Adventure, folder: Path, srd: Path) -> list[str]:
    """Every creature's srd_ref is a stat block in the SRD or the adventure's own
    creatures/ folder, as the game loads them."""
    problems = []
    for entity in adventure.entities:
        path = find_stat_block(entity.srd_ref, folder, srd)
        if path is None:
            problems.append(f"'{entity.id}' has no stat block '{entity.srd_ref}'")
            continue
        try:
            CreatureStatBlock.model_validate(yaml.safe_load(path.read_text()))
        except ValidationError as invalid:
            problems.append(f"{path.name}: {invalid.errors()[0]['msg']}")
    return problems


def one_sided_locks(adventure: Adventure) -> list[str]:
    """A door is two exits; the engine opens both at once, so both carry the
    same lock (BUILD_PLAN M8, the map convention)."""
    problems, seen = [], set()
    for lock in adventure.locks:
        other = adventure.other_side(lock.exit)
        if other is None or lock.exit in seen:
            continue
        seen |= {lock.exit, other}
        other_lock = adventure.lock(other)
        if other_lock is None:
            problems.append(f"'{lock.exit}' is locked but its other side '{other}' is not")
        elif other_lock.model_dump(exclude={"exit"}) != lock.model_dump(exclude={"exit"}):
            problems.append(f"the two sides of '{lock.exit}' and '{other}' are locked differently")
    return problems


def keys_behind_their_locks(adventure: Adventure) -> list[str]:
    problems = []
    for key in sorted({lock.key for lock in adventure.locks if lock.key is not None}):
        barred = frozenset(lock.exit for lock in adventure.locks if lock.key == key)
        if key not in explore(adventure, barred).items:
            problems.append(f"key '{key}' lies behind a lock it opens")
    return problems


@dataclass
class Reached:
    """What a hero can get to from the start: places, items and flags."""

    locations: set[str] = field(default_factory=set)
    items: set[str] = field(default_factory=set)
    flags: set[str] = field(default_factory=set)


def explore(adventure: Adventure, barred: frozenset[str] = frozenset()) -> Reached:
    """Walk from the start until nothing new opens: a lock opens with its key,
    by picking or forcing it, or once its flag is set. Exits in `barred` open
    only by other means than their key."""
    reached = Reached(locations={adventure.start_location})
    while True:
        before = (len(reached.locations), len(reached.items), len(reached.flags))
        here = reached.locations
        carriers = {e.id for e in adventure.entities if e.location in here} | {"party"}
        for item in adventure.items:
            if item.location in here or item.carried_by in carriers:
                reached.items.add(item.id)
                if item.on_take:
                    reached.flags.add(item.on_take.set_flag)
        checks = [c for loc in adventure.locations if loc.id in here for c in loc.checks]
        checks += [c for e in adventure.entities if e.location in here for c in e.checks]
        reached.flags |= {c.on_success.set_flag for c in checks}
        reached.flags |= {u.set_flag for loc in adventure.locations if loc.id in here
                          for u in loc.uses if u.item is None or u.item in reached.items}
        for loc in adventure.locations:
            if loc.id in here:
                reached.locations |= {e.to for e in loc.exits
                                      if opens(adventure.lock(e.id), reached, e.id in barred)}
        if before == (len(reached.locations), len(reached.items), len(reached.flags)):
            return reached


def opens(lock: Lock | None, reached: Reached, key_barred: bool) -> bool:
    if lock is None or not lock.locked:
        return True
    if lock.key is not None and lock.key in reached.items and not key_barred:
        return True
    return (lock.pick_dc is not None or lock.force_dc is not None
            or (lock.opens_on_flag is not None and lock.opens_on_flag in reached.flags))
