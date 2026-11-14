"""Scene context: only what the party can perceive (plan 3.5 step 1).
Undiscovered locations are named only by direction, and hidden items and exits
the party has not found, and what a creature carries, are left out, so neither
interpreter nor narrator can leak or target what the party has not seen."""

from pydantic import BaseModel

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.ports import LoreSnippet
from solo_dm.core.state.models import GameState
from solo_dm.core.turn.combat import active_combatant


class SceneExit(BaseModel):
    exit_id: str
    direction: str
    leads_to: str | None  # location name once discovered
    locked: bool
    stuck: bool = False  # closed but not locked: forced open, not unlocked (M7)


class SceneCreature(BaseModel):
    creature_id: str
    name: str
    attitude: str
    alive: bool


class SceneItem(BaseModel):
    item_id: str
    name: str
    description: str | None = None

    @classmethod
    def of(cls, adventure: Adventure, item_id: str) -> "SceneItem":
        item = adventure.item(item_id)
        return cls(item_id=item_id, name=item.name, description=item.description)


class ScenePartyMember(BaseModel):
    character_id: str
    name: str
    hp: int
    max_hp: int
    defeated: bool
    armor_class: int
    armor: str | None
    weapons: list[str]
    inventory: list[SceneItem]


class SceneHazard(BaseModel):
    """A trap or hazard here that the party has noticed and so avoids."""

    hazard_id: str
    name: str


class SceneSense(BaseModel):
    direction: str  # the exit it comes through
    senses: str


class SceneContext(BaseModel):
    location_id: str
    location_name: str
    description: str
    exits: list[SceneExit]
    nearby: list[SceneSense] = []
    hazards: list[SceneHazard] = []
    creatures: list[SceneCreature]
    items: list[SceneItem]
    party: list[ScenePartyMember]
    in_combat: bool
    active_combatant: str | None
    # Background for the tagged location, creatures and items here, and for what
    # the interpreter asked to look up. Context only: it never changes outcomes.
    lore: list[LoreSnippet] = []

    def valid_ids(self) -> set[str]:
        held = {i.item_id for m in self.party for i in m.inventory}
        return (
            {e.exit_id for e in self.exits}
            | {c.creature_id for c in self.creatures}
            | {i.item_id for i in self.items}
            | held
        )


def scene_tags(scene: SceneContext, adventure: Adventure) -> list[str]:
    """Tags of the location and of every creature and item the scene shows."""
    tags = list(adventure.location(scene.location_id).tags)
    for creature in scene.creatures:
        tags += adventure.entity(creature.creature_id).tags
    for item_id in [i.item_id for i in scene.items]:
        tags += adventure.item(item_id).tags
    return list(dict.fromkeys(tags))


def build_scene(state: GameState, adventure: Adventure) -> SceneContext:
    location = adventure.location(state.party_location)
    return SceneContext(
        location_id=location.id,
        location_name=location.name,
        description=location.description,
        exits=[
            SceneExit(
                exit_id=e.id,
                direction=e.direction,
                leads_to=adventure.location(e.to).name
                if e.to in state.discovered_locations
                else None,
                locked=e.id in state.locked_exits and not _stuck(adventure, e.id),
                stuck=e.id in state.locked_exits and _stuck(adventure, e.id),
            )
            for e in location.exits
            if e.id not in state.hidden_unfound
        ],
        nearby=[
            SceneSense(direction=e.direction, senses=adventure.location(e.to).senses)
            for e in location.exits
            if e.id not in state.hidden_unfound and adventure.location(e.to).senses
        ],
        hazards=[
            SceneHazard(hazard_id=h.id, name=h.name)
            for h in location.hazards
            if h.hidden is not None and h.id not in state.hidden_unfound
            and h.id not in state.sprung_hazards
        ],
        creatures=[
            SceneCreature(
                creature_id=c.creature_id, name=c.name, attitude=c.attitude, alive=c.alive
            )
            for c in state.creatures.values()
            if c.location == location.id
        ],
        items=[
            SceneItem.of(adventure, item_id)
            for item_id, where in state.items_on_floor.items()
            if where == location.id and item_id not in state.hidden_unfound
        ],
        party=[
            ScenePartyMember(
                character_id=m.character_id,
                name=m.name,
                hp=m.hp,
                max_hp=m.max_hp,
                defeated=m.defeated,
                armor_class=m.armor_class,
                armor=m.armor,
                weapons=[w.name for w in m.weapons],
                inventory=[SceneItem.of(adventure, i) for i in m.inventory],
            )
            for m in state.party.values()
        ],
        in_combat=state.in_combat,
        active_combatant=active_combatant(state),
    )


def _stuck(adventure: Adventure, exit_id: str) -> bool:
    lock = adventure.lock(exit_id)
    return lock is not None and lock.stuck
