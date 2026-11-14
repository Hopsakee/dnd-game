"""Adventure schema (plan 4.1). Validates the YAML and fails loudly when an id
is duplicated or a reference does not resolve."""

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, model_validator

from solo_dm.core.state.models import Ability, Attitude


class AdventureModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Hidden(AdventureModel):
    """Found by passive Perception on entering, or by a search (WIS check) vs dc."""

    dc: int = Field(ge=1)


class SetFlag(AdventureModel):
    set_flag: str


class CheckConsequence(AdventureModel):
    """What an ability-check fallback (plan 3.7) does here when the check succeeds.
    Matches a check with this ability (and skill, when given)."""

    ability: Ability
    skill: str | None = None
    # The DC the adventure states, if it states one (M7); otherwise Python sets it
    # from the interpreter's task category, as for any fallback (plan 3.7).
    dc: int | None = Field(default=None, ge=1)
    on_success: SetFlag
    # A challenge (Azzinax play test, 2026-11-14): with an id and a goal, the
    # interpreter sees the goal, and any attempt at it rolls this check.
    id: str | None = None
    goal: str | None = None


class ItemUse(AdventureModel):
    """Using this item here sets the flag (M7: the coin in the fountain).
    Locks with opens_on_flag open when it is set."""

    item: str
    set_flag: str
    used_up: bool = False


class SaveSpec(AdventureModel):
    ability: Ability
    dc: int = Field(ge=1)


class Hazard(AdventureModel):
    """A trap or hazard in a location (M7). With `hidden` it is a hidden thing:
    noticed (by passive Perception on entering, or a search) means avoided.
    Otherwise it springs once when the party enters: each member makes the
    saving throw, and takes the damage on a failure."""

    id: str
    name: str
    hidden: Hidden | None = None
    save: SaveSpec
    damage_dice: str
    damage_type: str


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
    checks: tuple[CheckConsequence, ...] = ()
    hazards: tuple[Hazard, ...] = ()
    uses: tuple[ItemUse, ...] = ()
    # What can be smelt or heard from the rooms next door. Keep it to things that
    # do not change in play (smoke, water, wind), not creatures that may die.
    senses: str | None = None


class EntityPlacement(AdventureModel):
    id: str
    srd_ref: str
    location: str
    attitude: Attitude
    tags: tuple[str, ...] = ()
    checks: tuple[CheckConsequence, ...] = ()
    # What it is doing when the party arrives ("sits sharpening a knife"); shown
    # until it turns hostile or dies, so the room description need not say it.
    activity: str | None = None
    # Creatures of one group fight together: attack one, and all turn hostile.
    group: str | None = None


class ItemEffect(AdventureModel):
    """What using the item does, wherever it is used; it is then used up (M7)."""

    heal: str  # dice, e.g. "2d4+2"


class OnTake(SetFlag):
    pass


PARTY = "party"  # carried_by this: the first party member starts with the item


class ItemPlacement(AdventureModel):
    """An item lies in a location or is carried by an entity (dropped on its body
    once the body is searched). Exactly one of location and carried_by is set."""

    id: str
    name: str
    # What the item looks and feels like. The narrator uses this and invents no
    # other properties (play-test flag 12).
    description: str | None = None
    location: str | None = None
    # An entity id, or "party": the hero starts with it (his own coins, M7).
    carried_by: str | None = None
    hidden: Hidden | None = None
    on_take: OnTake | None = None
    effect: ItemEffect | None = None
    tags: tuple[str, ...] = ()


class Lock(AdventureModel):
    exit: str
    locked: bool = True
    key: str | None = None
    pick_dc: int | None = None
    # A stuck door: forced open with Strength (Athletics) against this DC (M7).
    force_dc: int | None = None
    # Opened by a mechanism: when this flag is set (M7, e.g. an ItemUse).
    opens_on_flag: str | None = None

    @property
    def stuck(self) -> bool:
        """Only force opens it: no key and no lock to pick."""
        return self.force_dc is not None and self.key is None and self.pick_dc is None


class Guardian(AdventureModel):
    """Someone who brings a hero back to full hit points instead of a defeat,
    this many times per adventure (M7: Spiritus Magehunter)."""

    name: str
    rescues: int = Field(default=1, ge=1)


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
    guardian: Guardian | None = None

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

    def other_side(self, exit_id: str) -> str | None:
        """The exit back through the same door: the one way from the destination
        to here, or None when there are several (two doors between two rooms)."""
        origin = next(loc.id for loc in self.locations for e in loc.exits if e.id == exit_id)
        back = [e.id for e in self.location(self.exit(exit_id).to).exits if e.to == origin]
        return back[0] if len(back) == 1 else None

    def item(self, item_id: str) -> ItemPlacement:
        return next(i for i in self.items if i.id == item_id)

    def lock(self, exit_id: str) -> Lock | None:
        return next((lock for lock in self.locks if lock.exit == exit_id), None)

    def entity(self, entity_id: str) -> EntityPlacement | None:
        return next((e for e in self.entities if e.id == entity_id), None)

    def hidden_in(self, location_id: str) -> list[tuple[str, int]]:
        """(id, dc) of every hidden item and exit placed in this location."""
        items = [(i.id, i.hidden.dc) for i in self.items
                 if i.hidden and i.location == location_id]
        location = self.location(location_id)
        exits = [(e.id, e.hidden.dc) for e in location.exits if e.hidden]
        hazards = [(h.id, h.hidden.dc) for h in location.hazards if h.hidden]
        return items + exits + hazards


def _reference_problems(adventure: Adventure) -> list[str]:
    locations = {loc.id for loc in adventure.locations}
    exits = {e.id for loc in adventure.locations for e in loc.exits}
    items = {i.id for i in adventure.items}
    all_ids = [
        *[loc.id for loc in adventure.locations],
        *[e.id for loc in adventure.locations for e in loc.exits],
        *[h.id for loc in adventure.locations for h in loc.hazards],
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
        elif item.carried_by not in (None, PARTY, *entities):
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
    for loc in adventure.locations:
        problems += [f"'{loc.id}' uses unknown item '{u.item}'"
                     for u in loc.uses if u.item not in items]
    flags = {i.on_take.set_flag for i in adventure.items if i.on_take} | {
        u.set_flag for loc in adventure.locations for u in loc.uses
    } | {
        c.on_success.set_flag
        for placed in (*adventure.locations, *adventure.entities)
        for c in placed.checks
    }
    problems += [f"lock on '{lock.exit}' opens on flag '{lock.opens_on_flag}', which is never set"
                 for lock in adventure.locks
                 if lock.opens_on_flag is not None and lock.opens_on_flag not in flags]
    if adventure.win_condition.flag not in flags:
        problems.append(f"win flag '{adventure.win_condition.flag}' is never set")
    return problems
