"""The node map (plan 5.2): discovered rooms on a grid, placed by the direction
of the exits between them, the party's room highlighted."""

import hashlib

from fasthtml.common import NotStr

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.state.models import GameState
from solo_dm.core.turn.player_view import RevealedMap, known_map

STEP = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0),
        "northeast": (1, -1), "northwest": (-1, -1), "southeast": (1, 1),
        "southwest": (-1, 1), "up": (1, -1), "down": (-1, 1)}
CELL_W, CELL_H, BOX_W, BOX_H = 150, 90, 124, 44
DOOR = 14


def grid_positions(state: GameState, adventure: Adventure) -> dict[str, tuple[int, int]]:
    """A grid cell per discovered room. The first room is the origin; each room
    reached through an exit sits one step that way, or the nearest free cell when
    that one is taken (adventures need not be drawn on a grid)."""
    known = known_map(state, adventure)
    if not known.rooms:
        return {}
    placed = {known.rooms[0].location_id: (0, 0)}
    taken = {(0, 0)}
    queue = [known.rooms[0].location_id]
    while queue:
        here = queue.pop(0)
        for link in (k for k in known.links if k.from_id == here and k.to_id not in placed):
            dx, dy = STEP.get(link.direction, (1, 1))
            x, y = placed[here]
            cell = _free(x + dx, y + dy, taken)
            placed[link.to_id] = cell
            taken.add(cell)
            queue.append(link.to_id)
    for room in known.rooms:  # reached only through an exit not yet known
        if room.location_id not in placed:
            cell = _free(0, max(y for _, y in taken) + 1, taken)
            placed[room.location_id] = cell
            taken.add(cell)
    return placed


def _door_spot(x1: int, y1: int, x2: int, y2: int) -> tuple[int, int]:
    """Where the line leaves the first room's grid cell: the gap next to that
    room. The middle of the line can lie on a room it passes over."""
    dx, dy = x2 - x1, y2 - y1
    t = min(CELL_W / 2 / abs(dx) if dx else 1.0, CELL_H / 2 / abs(dy) if dy else 1.0, 0.5)
    return round(x1 + dx * t), round(y1 + dy * t)


def _free(x: int, y: int, taken: set[tuple[int, int]]) -> tuple[int, int]:
    for radius in range(0, 10):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if (x + dx, y + dy) not in taken:
                    return x + dx, y + dy
    raise ValueError("no free cell near the room")


def map_svg(state: GameState, adventure: Adventure):
    known = known_map(state, adventure)
    cells = grid_positions(state, adventure)
    if not cells:
        return NotStr("<p>No rooms discovered yet.</p>")
    min_x = min(x for x, _ in cells.values())
    min_y = min(y for _, y in cells.values())
    width = (max(x for x, _ in cells.values()) - min_x + 1) * CELL_W
    height = (max(y for _, y in cells.values()) - min_y + 1) * CELL_H

    def centre(location_id: str) -> tuple[int, int]:
        x, y = cells[location_id]
        return (x - min_x) * CELL_W + CELL_W // 2, (y - min_y) * CELL_H + CELL_H // 2

    parts, doors = [], []
    pairs: dict[frozenset, list] = {}
    for link in known.links:  # a passage known from both sides is one line
        pairs.setdefault(frozenset((link.from_id, link.to_id)), []).append(link)
    for sides in pairs.values():
        (x1, y1), (x2, y2) = centre(sides[0].from_id), centre(sides[0].to_id)
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="link"/>')
        if any(s.door for s in sides):
            shut = " locked" if any(s.shut for s in sides) else ""
            mx, my = _door_spot(x1, y1, x2, y2)
            doors.append(f'<rect class="door{shut}" x="{mx - DOOR // 2}" y="{my - DOOR // 2}" '
                         f'width="{DOOR}" height="{DOOR}"><title>door</title></rect>')
    for room in known.rooms:
        cx, cy = centre(room.location_id)
        cls = "room current" if room.current else "room"
        parts.append(
            f'<g class="{cls}"><title>{_esc(room.name)}</title>'
            f'<rect x="{cx - BOX_W // 2}" y="{cy - BOX_H // 2}" width="{BOX_W}" '
            f'height="{BOX_H}" rx="6"/>'
            f'<text x="{cx}" y="{cy + 5}" text-anchor="middle">{_esc(room.name)}</text></g>')
    parts += doors  # on top of the lines, between the rooms
    return NotStr(
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Map of discovered rooms" '
        f'xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>')


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def player_map_svg(seen: RevealedMap, image_url: str, size: tuple[int, int]):
    """The book's player map, cut to the parts the party has seen (Azzinax flag 22),
    with the party's location lit up. The image is the whole map; a player who
    opens its address sees all of it (no image library in the box to crop it)."""
    width, height = size
    x, y, w, h = seen.view
    w, h = min(w, width - x), min(h, height - y)

    def rects(cls: str, found) -> str:
        return "".join(f'<rect class="{cls}" x="{rx}" y="{ry}" width="{rw}" height="{rh}"/>'
                       for rx, ry, rw, rh in found)

    # One id per cut: maps typed into the play log earlier keep their own.
    clip = "seen-" + hashlib.sha1(str(seen.seen).encode()).hexdigest()[:10]
    return NotStr(
        f'<svg viewBox="{x} {y} {w} {h}" role="img" aria-label="The map, where you have been" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<defs><clipPath id="{clip}">{rects("seen", seen.seen)}</clipPath></defs>'
        f'<rect class="fog" x="{x}" y="{y}" width="{w}" height="{h}"/>'
        f'<image href="{image_url}" x="0" y="0" width="{width}" height="{height}" '
        f'clip-path="url(#{clip})"/>{rects("here", seen.here)}</svg>')
