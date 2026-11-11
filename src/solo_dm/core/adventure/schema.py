"""Adventure schema (plan 4.1). Validates the YAML and fails loudly when an id
is duplicated or a reference does not resolve."""

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, model_validator

from solo_dm.core.state.models import Attitude


class AdventureModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Hidden(AdventureModel):
    """Found by passive Perception on entering, or by a search (WIS check) vs dc."""

    dc: int = Field(ge=1)


class Exit(AdventureModel):
    id: str
    to: str
    direction: str
    hidden: Hidden | None = None


class Location(AdventureModel):
    id: str
    name: str
    description: str
    exits: tuple[Exit, ...] = ()
    tags: tuple[str, ...] = ()


class EntityPlacement(AdventureModel):
    id: str
    srd_ref: str
    location: str
    attitude: Attitude
    tags: tuple[str, ...] = ()


class OnTake(AdventureModel):
    set_flag: str


class ItemPlacement(AdventureModel):
    """An item lies in a location or is carried by an entity (dropped on its body
    once the body is searched). Exactly one of location and carried_by is set."""

    id: str
    name: str
    location: str | None = None
    carried_by: str | None = None
    hidden: Hidden | None = None
    on_take: OnTake | None = None


class Lock(AdventureModel):
    exit: str
    locked: bool = True
    key: str | None = None
    pick_dc: int | None = None


class WinCondition(AdventureModel):
    flag: str


class Adventure(AdventureModel):
    id: str
    title: str
    start_location: str
    win_condition: WinCondition
    locations: tuple[Location, ...]
    entities: tuple[EntityPlacement, ...] = ()
    items: tuple[ItemPlacement, ...] = ()
    locks: tuple[Lock, ...] = ()

    @model_validator(mode="after")
    def _references_resolve(self) -> "Adventure":
        problems = _reference_problems(self)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def location(self, location_id: str) -> Location:
        return next(loc for loc in self.locations if loc.id == location_id)

    def exit(self, exit_id: str) -> Exit:
        return next(e for loc in self.locations for e in loc.exits if e.id == exit_id)

    def item(self, item_id: str) -> ItemPlacement:
        return next(i for i in self.items if i.id == item_id)

    def lock(self, exit_id: str) -> Lock | None:
        return next((lock for lock in self.locks if lock.exit == exit_id), None)

    def hidden_in(self, location_id: str) -> list[tuple[str, int]]:
        """(id, dc) of every hidden item and exit placed in this location."""
        items = [(i.id, i.hidden.dc) for i in self.items
                 if i.hidden and i.location == location_id]
        exits = [(e.id, e.hidden.dc) for e in self.location(location_id).exits if e.hidden]
        return items + exits


def _reference_problems(adventure: Adventure) -> list[str]:
    locations = {loc.id for loc in adventure.locations}
    exits = {e.id for loc in adventure.locations for e in loc.exits}
    items = {i.id for i in adventure.items}
    all_ids = [
        *[loc.id for loc in adventure.locations],
        *[e.id for loc in adventure.locations for e in loc.exits],
        *[e.id for e in adventure.entities],
        *[i.id for i in adventure.items],
    ]
    problems = [f"duplicate id '{i}'" for i, n in Counter(all_ids).items() if n > 1]
    if adventure.start_location not in locations:
        problems.append(f"start_location '{adventure.start_location}' is not a location")
    for loc in adventure.locations:
        problems += [
            f"exit '{e.id}' leads to unknown location '{e.to}'"
            for e in loc.exits
            if e.to not in locations
        ]
    entities = {e.id for e in adventure.entities}
    for item in adventure.items:
        if item.location is None and item.carried_by is None:
            problems.append(f"'{item.id}' needs a location or carried_by")
        elif item.location is not None and item.carried_by is not None:
            problems.append(f"'{item.id}' has both a location and carried_by")
        elif item.carried_by is not None and item.carried_by not in entities:
            problems.append(f"'{item.id}' is carried by unknown entity '{item.carried_by}'")
        if item.carried_by is not None and item.hidden is not None:
            problems.append(f"'{item.id}' is carried, so it cannot be hidden")
    for placed in (*adventure.entities, *adventure.items):
        if placed.location is not None and placed.location not in locations:
            problems.append(f"'{placed.id}' is in unknown location '{placed.location}'")
    for lock in adventure.locks:
        if lock.exit not in exits:
            problems.append(f"lock exit '{lock.exit}' is not an exit")
        if lock.key is not None and lock.key not in items:
            problems.append(f"lock key '{lock.key}' is not an item")
    flags = {i.on_take.set_flag for i in adventure.items if i.on_take}
    if adventure.win_condition.flag not in flags:
        problems.append(f"win flag '{adventure.win_condition.flag}' is never set")
    return problems
