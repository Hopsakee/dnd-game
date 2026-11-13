# M7 test book: The Secrets of Skyhorn Lighthouse

Supplied by Jelle 2026-11-13 as the example adventure book to turn into a playable game. Decided by Jelle 2026-11-13: postponed to M7 (after M6), plan order unchanged; no spike now.

- Where: ~/transport/dndgame/1060290-The_Secrets_of_Skyhorn_Lighhouse_V8-1.zip (124 MB: PDF, print-friendly PDF, maps, combat cards, Fantasy Grounds .mod).
- Copyright (Jelle 2026-11-13): purchased product (Arcane Library, OGL plus own text). A converted adventure lives OUTSIDE git (e.g. gitignored adventures/private/); the repo gets code and findings only.
- Sources (Jelle 2026-11-13: use both, compare): the PDF is the real path; the .mod's db.xml is clean structured XML (encounter = story sections, npc 16, item 4, treasureparcels 8, battle 8) and serves as a check on what PDF extraction loses.
- Reading the PDF in the box: pymupdf / pymupdf4llm from the wheel store (as _EXTRACT_TEXT does); `uv run --no-project --with pymupdf4llm`. 23 pages. Measured 2026-11-13: ligatures fl/fi come out as "2" ("2laps", "2irst"): an extraction eval case. Poppler and pypdf are absent and not needed.
- Size: about 6,400 words in the FG story text; scenes: harbour rumours, ship fight (water elemental), lighthouse siege (eelfolk), caves (areas 5-9: sharks, hostages, summoning room), aftermath.
- Engine gaps it exposes (engine as of PR #11, 2026-11-13): party of 4-5 at level 5; spells and magic items (Bead of Force, Dagger of Venom, Potion of Water Breathing, Bowl of Commanding Water Elementals); swimming, underwater combat, breath; morale (sharks flee below 15 HP); allied NPCs (ship crew, Lucien) and dialogue NPCs with goals; travel scenes by ship; non-SRD monsters (four eelfolk) with their own stat blocks; treasure parcels as loot; maps as images only.
