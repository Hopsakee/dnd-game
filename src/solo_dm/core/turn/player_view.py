"""What the player's screens show, shared by the terminal and the web app:
shortcut expansion and the map of discovered rooms. Built from state, so it
never names a room or a hidden exit the party has not found."""

from collections.abc import Mapping

from pydantic import BaseModel

from solo_dm.core.adventure.map_schema import AdventureMap
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
    door = "door, " if e.door else ""
    return f"{e.direction} ({door}{e.leads_to or 'unexplored'}{state})"


class MapRoom(BaseModel):
    location_id: str
    name: str
    current: bool


class MapLink(BaseModel):
    from_id: str
    to_id: str
    direction: str
    door: bool = False
    shut: bool = False  # locked, stuck or sealed: not passable yet


class KnownMap(BaseModel):
    rooms: list[MapRoom]  # in the order they were discovered
    links: list[MapLink]  # one per known exit, so a two-way passage appears twice


def known_map(state: GameState, adventure: Adventure) -> KnownMap:
    rooms, links = [], []
    for location_id in state.discovered_locations:
        location = adventure.location(location_id)
        rooms.append(MapRoom(location_id=location_id, name=location.name,
                             current=location_id == state.party_location))
        links += [MapLink(from_id=location_id, to_id=e.to, direction=e.direction, door=e.door,
                          shut=e.id in state.locked_exits)
                  for e in location.exits
                  if e.to in state.discovered_locations and e.id not in state.hidden_unfound]
    return KnownMap(rooms=rooms, links=links)


Rect = tuple[int, int, int, int]  # x, y, width, height in image pixels


class RevealedMap(BaseModel):
    seen: list[Rect]  # discovered locations and the openings out of them
    here: list[Rect]  # the party's location; empty off the map
    view: Rect  # what is seen, with a cell of margin


def revealed_map(state: GameState, adventure_map: AdventureMap,
                 within: Mapping[str, str] | None = None) -> RevealedMap | None:
    """The parts of the book's player map the party has seen, or None when the
    adventure has none or nothing on it is discovered yet (Azzinax flag 22).
    `within`: a place inside a room (M8.5) shows as that room."""
    within = within or {}
    if adventure_map.player_image is None or adventure_map.cell_px is None:
        return None
    size = adventure_map.cell_px

    def pixels(c0: int, r0: int, c1: int, r1: int) -> Rect:
        x, y = round(c0 * size), round(r0 * size)
        return x, y, round((c1 + 1) * size) - x, round((r1 + 1) * size) - y

    def cells_of(location_id: str) -> list[Rect]:
        location = adventure_map.locations.get(within.get(location_id, location_id))
        return [pixels(*cell) for cell in location.cells] if location else []

    seen: list[Rect] = []
    for location_id in state.discovered_locations:
        location_id = within.get(location_id, location_id)
        location = adventure_map.locations.get(location_id)
        if location is None:
            continue
        seen += cells_of(location_id)
        seen += [pixels(int(o.at[0] // size), int(o.at[1] // size),
                        int(o.at[0] // size), int(o.at[1] // size))
                 for o in location.openings if o.at is not None]
    seen = list(dict.fromkeys(seen))
    if not seen:
        return None
    x0 = max(0, min(x for x, _, _, _ in seen) - round(size))
    y0 = max(0, min(y for _, y, _, _ in seen) - round(size))
    x1 = max(x + w for x, _, w, _ in seen) + round(size)
    y1 = max(y + h for _, y, _, h in seen) + round(size)
    return RevealedMap(seen=seen, here=cells_of(state.party_location),
                       view=(x0, y0, x1 - x0, y1 - y0))
