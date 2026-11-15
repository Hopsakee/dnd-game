"""Builds the repo's own test book for M8, "The Miller's Cellar" (an original
adventure written for this repo, free of anyone's copyright):

- book/map_dm.png       the DM map: grid, room numbers, feature letters
- book/map_player.png   the same map without numbers or letters (also gold/player_map.png)
- book/old_grist.png    a stat block as a picture, as books often print them
- book/book.pdf         book/book.md with the pictures, via pandoc and xelatex

The map is drawn from LAYOUT below, so the gold map.yaml's cells and opening
positions agree with the picture. Needs pandoc, xelatex and chromium (the box has
all three). Run from the repo root:

    python3 evals/millers_cellar/build.py
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
BOOK = HERE / "book"
CELL = 40
COLS, ROWS = 20, 15

# Floor: (first column, first row, last column, last row), per location.
LAYOUT = {
    "1": [(1, 2, 6, 6)],
    "2": [(12, 2, 17, 6)],
    "3": [(13, 9, 17, 12)],
    "4": [(1, 9, 5, 12)],
    "C1": [(7, 4, 11, 4)],
    "C2": [(3, 7, 3, 8)],
    "C3": [(15, 7, 15, 8)],
    "C4": [(6, 10, 8, 10)],
    "C5": [(9, 10, 12, 10)],
    "C6": [(9, 11, 9, 13)],
}
# Doors: pixel position of the door's middle and whether the wall runs across
# (horizontal) or up and down (vertical).
DOORS = [((280, 180), "v"), ((480, 180), "v"), ((620, 280), "h"), ((620, 360), "h"),
         ((520, 420), "v"), ((240, 420), "v")]
STAIRS = (1, 4)  # the way in from the yard: the west wall of room 1, row 4
LETTERS = {"a": (9, 4), "b": (9, 13)}


def svg(labels: bool) -> str:
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{COLS * CELL}" '
           f'height="{ROWS * CELL}" font-family="DejaVu Serif">',
           '<rect width="100%" height="100%" fill="#3d5a6c"/>']
    for rects in LAYOUT.values():
        for c0, r0, c1, r1 in rects:
            out.append(f'<rect x="{c0 * CELL}" y="{r0 * CELL}" width="{(c1 - c0 + 1) * CELL}" '
                       f'height="{(r1 - r0 + 1) * CELL}" fill="#fbf8f0"/>')
    for x in range(0, COLS * CELL, CELL):
        out.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{ROWS * CELL}" '
                   'stroke="#3d5a6c" stroke-opacity="0.35"/>')
    for y in range(0, ROWS * CELL, CELL):
        out.append(f'<line x1="0" y1="{y}" x2="{COLS * CELL}" y2="{y}" '
                   'stroke="#3d5a6c" stroke-opacity="0.35"/>')
    for (x, y), wall in DOORS:
        w, h = (10, 26) if wall == "v" else (26, 10)
        out.append(f'<rect x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" '
                   'fill="#8a5a2b" stroke="#2b1a0b" stroke-width="2"/>')
    c, r = STAIRS
    for i in range(4):  # stairs going up out of the map, west of room 1
        out.append(f'<rect x="{c * CELL - 36 + i * 9}" y="{r * CELL + 4}" width="7" '
                   f'height="{CELL - 8}" fill="#fbf8f0" stroke="#3d5a6c"/>')
    if labels:
        for name, rects in LAYOUT.items():
            if name.startswith("C"):
                continue
            c0, r0, c1, r1 = rects[0]
            cx, cy = (c0 + c1 + 1) * CELL / 2, (r0 + r1 + 1) * CELL / 2
            out.append(f'<text x="{cx}" y="{cy + 12}" font-size="34" text-anchor="middle" '
                       f'font-weight="bold" fill="#7a1f1f">{name}</text>')
        for letter, (c, r) in LETTERS.items():
            out.append(f'<text x="{c * CELL + 20}" y="{r * CELL + 28}" font-size="24" '
                       f'text-anchor="middle" font-style="italic" fill="#1f4f7a">{letter}</text>')
    out.append("</svg>")
    return "\n".join(out)


STAT_BLOCK = """<html><body style="margin:0;background:#f4ead2;font-family:'DejaVu Serif'">
<div style="width:560px;padding:24px;border-top:6px solid #7a1f1f;border-bottom:6px solid #7a1f1f">
<div style="font-size:30px;font-weight:bold;color:#7a1f1f">Old Grist</div>
<div style="font-style:italic;margin-bottom:10px">Medium Humanoid, Neutral Evil</div>
<div><b>AC</b> 13 (leather) &nbsp; <b>HP</b> 16 (3d8 + 3) &nbsp; <b>Speed</b> 9 m</div>
<div><b>Initiative</b> +1</div>
<table style="width:100%;margin:10px 0;text-align:center;border-collapse:collapse">
<tr><th>STR</th><th>DEX</th><th>CON</th><th>INT</th><th>WIS</th><th>CHA</th></tr>
<tr><td>14 (+2)</td><td>12 (+1)</td><td>12 (+1)</td><td>11 (+0)</td><td>10 (+0)</td>
<td>13 (+1)</td></tr></table>
<div><b>Senses</b> Passive Perception 10 &nbsp; <b>Languages</b> Common</div>
<div><b>CR</b> 1/2</div>
<div style="font-size:22px;color:#7a1f1f;border-bottom:1px solid #7a1f1f;margin-top:12px">
Actions</div>
<div><b><i>Cleaver.</i></b> <i>Melee Attack Roll:</i> +4, reach 1.5 m. <i>Hit:</i> 6 (1d8 + 2)
Slashing damage.</div>
<div style="margin-top:6px"><b><i>Bribe.</i></b> Grist offers the hero a share of the take
to walk away. He never means it.</div>
</div></body></html>"""


def screenshot(source: Path, out: Path, width: int, height: int) -> None:
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(["chromium", "--headless", "--no-sandbox", "--disable-gpu",
                        f"--user-data-dir={profile}", "--hide-scrollbars",
                        f"--window-size={width},{height}", f"--screenshot={out}",
                        source.as_uri()], check=True, capture_output=True)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for name, labels in (("map_dm", True), ("map_player", False)):
            source = work / f"{name}.svg"
            source.write_text(svg(labels))
            screenshot(source, BOOK / f"{name}.png", COLS * CELL, ROWS * CELL)
        source = work / "old_grist.html"
        source.write_text(STAT_BLOCK)
        screenshot(source, BOOK / "old_grist.png", 608, 420)
    shutil.copy(BOOK / "map_player.png", HERE / "gold" / "player_map.png")
    subprocess.run(["pandoc", "book.md", "-o", "book.pdf", "--pdf-engine=xelatex",
                    "-V", "geometry:a5paper,margin=15mm", "-V", "mainfont=DejaVu Serif",
                    "-V", "fontsize=10pt"], cwd=BOOK, check=True)


if __name__ == "__main__":
    main()
