"""The stage files in an ingest folder (dnd-adventures/ingest/<book>/), one per
skill of the adventure-converter agent (BUILD_PLAN M8). Built from the engine's
own adventure models, so a stage holds exactly what the engine reads:

| file            | skill                | holds                                          |
|-----------------|----------------------|------------------------------------------------|
| map.yaml        | map                  | rooms, corridors, openings (AdventureMap)      |
| locations.yaml  | map                  | the adventure's id, title, start; each place's |
|                 |                      | name and description (exits come from the map) |
| creatures.yaml  | creatures            | who is where; the guardian; own stat blocks in |
|                 |                      | creatures/<stat_block_id>.yaml                 |
| items.yaml      | items-locks-hazards  | items, locks, hazards, uses, the win flag      |
| challenges.yaml | challenges           | every check, at a location or a creature       |
"""

from pydantic import Field

from solo_dm.core.adventure.schema import (
    AdventureModel,
    CheckConsequence,
    EntityPlacement,
    Guardian,
    Hazard,
    ItemPlacement,
    ItemUse,
    Lock,
    WinCondition,
)


class PlaceText(AdventureModel):
    id: str  # a map location or off-map place
    name: str
    description: str
    tags: tuple[str, ...] = ()
    senses: str | None = None
    # Exits found only by searching: opening id -> the search DC.
    hidden_exits: dict[str, int] = {}


class LocationsStage(AdventureModel):
    id: str
    title: str
    start_location: str
    locations: tuple[PlaceText, ...]


class Creature(EntityPlacement):
    # A check that talks a creature round lives in challenges.yaml, at the creature.
    checks: tuple[CheckConsequence, ...] = Field(default=(), max_length=0)


class CreaturesStage(AdventureModel):
    guardian: Guardian | None = None
    creatures: tuple[Creature, ...] = ()


class PlacedHazard(Hazard):
    at: str  # location id


class PlacedUse(ItemUse):
    at: str  # location id


class ItemsStage(AdventureModel):
    win_condition: WinCondition
    items: tuple[ItemPlacement, ...] = ()
    locks: tuple[Lock, ...] = ()
    hazards: tuple[PlacedHazard, ...] = ()
    uses: tuple[PlacedUse, ...] = ()


class Challenge(CheckConsequence):
    at: str  # location or creature id


class ChallengesStage(AdventureModel):
    challenges: tuple[Challenge, ...] = ()


STAGES = {
    "locations": ("locations.yaml", LocationsStage),
    "creatures": ("creatures.yaml", CreaturesStage),
    "items": ("items.yaml", ItemsStage),
    "challenges": ("challenges.yaml", ChallengesStage),
}
