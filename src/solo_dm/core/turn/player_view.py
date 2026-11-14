"""What the player's screens show, shared by the terminal and the web app:
shortcut expansion and the map of discovered rooms. Built from state, so it
never names a room or a hidden exit the party has not found."""

from pydantic import BaseModel

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.state.models import GameState
from solo_dm.core.turn.scene import SceneExit

# Typed often, so short (play-test flag 10, 2026-11-13). Only the first word is
# expanded: "a goblin" is "attack goblin".
SHORTCUTS = {"a": "attack", "n": "go north", "s": "go south", "e": "go east", "w": "go west"}


def expand_shortcut(line: str) -> str:
    first, _, rest = line.partition(" ")
    if first.lower() not in SHORTCUTS:
        return line
    return f"{SHORTCUTS[first.lower()]} {rest}".strip()


def exit_label(e: SceneExit) -> str:
    """'north (Pillared Hall, locked)', as the room view lists an exit."""
    state = ", locked" if e.locked else ", stuck" if e.stuck else ""
    return f"{e.direction} ({e.leads_to or 'unexplored'}{state})"


class MapRoom(BaseModel):
    location_id: str
    name: str
    current: bool


class MapLink(BaseModel):
    from_id: str
    to_id: str
    direction: str


class KnownMap(BaseModel):
    rooms: list[MapRoom]  # in the order they were discovered
    links: list[MapLink]  # one per known exit, so a two-way passage appears twice


def known_map(state: GameState, adventure: Adventure) -> KnownMap:
    rooms, links = [], []
    for location_id in state.discovered_locations:
        location = adventure.location(location_id)
        rooms.append(MapRoom(location_id=location_id, name=location.name,
                             current=location_id == state.party_location))
        links += [MapLink(from_id=location_id, to_id=e.to, direction=e.direction)
                  for e in location.exits
                  if e.to in state.discovered_locations and e.id not in state.hidden_unfound]
    return KnownMap(rooms=rooms, links=links)
