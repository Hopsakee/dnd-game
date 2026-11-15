"""Draws adventures/scenarios/player_map/player_map.png: 20 px cells, blue rock,
white floor, one door. Usage: python3 scripts/draw_player_map_scenario.py <out.png>"""
import struct
import sys
import zlib

W, H, C = 200, 120, 20
FLOOR = [(1, 1, 3, 4), (5, 2, 6, 2), (7, 1, 8, 4)]  # hall, passage, vault
DOOR = (4, 2)
def colour(x, y):
    c, r = x // C, y // C
    if (c, r) == DOOR:
        inner = 4 <= x % C < 16 and 6 <= y % C < 14
        edge = x % C in (4, 15) or y % C in (6, 13)
        return (52, 152, 202) if inner and edge else (255, 255, 255)
    if any(c0 <= c <= c1 and r0 <= r <= r1 for c0, r0, c1, r1 in FLOOR):
        return (52, 152, 202) if x % C == 0 or y % C == 0 else (255, 255, 255)
    return (52, 152, 202)
raw = b"".join(b"\0" + bytes(v for x in range(W) for v in colour(x, y)) for y in range(H))
def chunk(t, d):
    return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
open(sys.argv[1], "wb").write(png)
