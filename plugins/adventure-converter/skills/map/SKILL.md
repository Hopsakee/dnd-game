---
name: map
description: The map step of converting an adventure for solo-dm. Reads the book's map into map.yaml (rooms, corridors, every opening and the opening it meets, cells on the player map) and writes locations.yaml (the adventure's id, title, start and each place's name and description). Use in the adventure-converter's step 2.
---

# Map: map.yaml and locations.yaml

Exits are not written by hand: `assemble` makes every opening in `map.yaml` an
exit. So the map step decides how the dungeon hangs together, and an error here
breaks everything after it.

Schemas: `adventure-ingest schema map` and `adventure-ingest schema locations`.
Example: `../dnd-game/evals/millers_cellar/stages/map.yaml` and
`locations.yaml`, drawn from `book/map_dm.png`.

## The convention (Jelle, 2026-11-14)

- **Rooms keep the book's number:** `room1`, `room2`, ... An opening is
  named after its room's number plus a letter: `5a`, `5b`.
- **A room's openings are lettered clockwise,** starting at the west end of
  the north wall: north wall west to east, east wall north to south, south
  wall east to west, west wall south to north.
- **Corridors are locations of their own,** cut at every junction, numbered
  `c1`, `c2`, ... in reading order of their north-most, then west-most cell.
  Their openings (`c3a`, `c3b`) are lettered in reading order of position
  (north first, then west). At a junction each corridor gets one opening per
  corridor it meets, ordered by that corridor's number.
- **Every corridor stays a location, also an empty one.** Folding an empty
  corridor away tells the player that the others hold something, and distance
  matters (what can be heard from where).
- **The map's small letters** (a, c, e, ...) are features in a corridor, not
  its name: list them under `features` of the corridor they lie in.
- **Every opening names the opening it meets** (`5d` meets `3b`, and `3b` meets
  `5d`). Partners have the same `kind` and, when both have one, the same `at`.
- **kind:** `door` (any door, also a locked, stuck or secret one), `archway`
  (an open doorway or a corridor ending in a room), `junction` (corridor meets
  corridor), `outside` (the way out of the map).
- **direction** is the button the player sees. Rooms: the wall the opening is
  in; two openings on one wall: the one nearer a corner takes that corner's
  diagonal (`northwest`). Corridors: the way towards that end; unique within
  the corridor.
- **at:** the opening's pixel position on the map image `[x, y]`: a door's
  middle, or the point where corridors meet.
- **Off the map** (`off_map`): places the adventure starts or passes through
  that the map does not show (a mill yard, a road). Their openings are
  named `<place>_a`, `<place>_b` and have no `at`. Letter them like a room's,
  clockwise by direction: north, east, south, west (an east opening comes
  before a west one). Lesson from the Azzinax trial's eval, 2026-11-15.

## The player map

If the book has a player map (the same drawing without numbers and secrets),
set `player_image` to its file name and `cell_px` to one grid cell in pixels,
and give every room and corridor its `cells`: rectangles
`[first column, first row, last column, last row]` of floor cells, counted
from 0 at the top left. Every floor cell belongs to exactly one location; door
cells are not floor. The image files are not committed: name them only.

Measure, do not guess: find the grid's pitch from the image's size and the
number of squares, then check two far-apart grid lines. pymupdf (in dnd-game's
environment) reads pixels: `uv run --project ../dnd-game python -c "import pymupdf;
p = pymupdf.Pixmap('<file>'); print(p.width, p.height, p.pixel(x, y))"`. To
read a crowded part, render a crop larger with `pymupdf` and read that picture.

## locations.yaml

- `id` (snake case), `title`, `start_location` (where the book starts the hero,
  often off the map).
- One entry per place in `map.yaml`, `locations` and `off_map` alike, in book
  order (off-map places first when the story starts there).
- `name`: the book's room name, or a short one of yours ("North Passage").
- `description`: what the hero sees on entering, two to four sentences in your
  own words: the room, its exits as the book describes them (wall and kind of
  door). Leave out creatures (they move and die; they have their own field),
  anything hidden (it has its own field and DC) and anything the hero has not
  yet learnt.
- `senses`: what can be heard or smelt from next door, only for things that do
  not change in play (water, smoke).
- `hidden_exits`: `{opening id: DC}` for a secret door found by searching.
- `tags`: only when the book groups places (a smugglers' hideout).

## Ask Jelle when

- An opening's partner is unclear (a door drawn between a room and a corridor
  that also touches another room).
- The book's text and its map disagree about a door or archway.
- The start is not on the map and the book does not say how the hero gets in.

## Before you go on

```bash
uv run --project ../dnd-game adventure-ingest check map ingest/<book_id>
uv run --project ../dnd-game adventure-ingest check locations ingest/<book_id>
```

Both must pass. Then count: every numbered room on the map is a location, and
every door drawn on the map is an opening of kind `door` on both sides.
