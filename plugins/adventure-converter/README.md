# adventure-converter

A Claude Code plugin that converts a published D&D adventure (a PDF and its
map) into an adventure solo-dm can play: one agent, run as the session so it can
ask you whenever the book leaves a judgement open, and one skill per domain
(BUILD_PLAN § 8 M8).

| Part | Writes |
|---|---|
| agent `adventure-converter` | the order of the steps, `questions.md`, and when to ask you |
| skill `map` | `map.yaml` (rooms, corridors, openings, cells) and `locations.yaml` |
| skill `creatures` | `creatures.yaml` and `creatures/<id>.yaml` stat blocks |
| skill `items-locks-hazards` | `items.yaml`: items, locks, hazards, uses, the win flag |
| skill `challenges` | `challenges.yaml`: every check that sets a flag |

The skills call `uv run adventure-ingest` (in `src/adventure_ingest/`) for
everything that is code: `extract`, `schema`, `check`, `assemble`, `verify`,
`eval`. The plugin holds no book text; its examples are dnd-game's own test
book in `evals/millers_cellar/`.

## Before the first run

- dnd-game and dnd-adventures cloned side by side (`~/src/dnd-game`,
  `~/src/dnd-adventures`), and `uv sync` run once in dnd-game.
- The book's PDF and map images somewhere on disk. They stay out of git.

## Start it

From the dnd-adventures root, so the stage files land in `ingest/<book_id>/`:

```bash
cd ~/src/dnd-adventures
claude --plugin-dir ../dnd-game/plugins/adventure-converter \
       --agent adventure-converter:adventure-converter
```

Then tell it the book, for example: "Convert ~/Downloads/The_Goblin_Cave.pdf,
map ~/Downloads/goblin_cave_map_dm.jpg. Book id: the_goblin_cave."

Verified 2026-11-15 with Claude Code 2.1.325 in the box: the session starts as
the agent and lists its four skills (`claude plugin validate
plugins/adventure-converter --strict` passes too). The agent's name needs the
plugin prefix (`adventure-converter:adventure-converter`).

Use your strongest model for a conversion (BUILD_PLAN § 10.2: Fable for running
the converter), for example `--model fable`.

### Without you at the keyboard

A run that may not ask you anything writes each question with the guess it
took into `questions.md` and goes on (this is how the trial conversion of
Azzinax was made):

```bash
claude -p "Convert <pdf> with map <png>, book id <id>. Nobody can answer questions in this run." \
       --plugin-dir ../dnd-game/plugins/adventure-converter \
       --agent adventure-converter:adventure-converter \
       --add-dir ../dnd-game <folder of the book> \
       --permission-mode acceptEdits \
       --allowedTools "Bash(uv run *)" "Bash(mkdir *)" "Bash(ls *)" Read Write Edit Glob Grep Skill
```

`--add-dir` lets it read dnd-game's examples and the book's folder; without it,
listing those folders is refused (seen in the trial run, which worked around it).

Give it a folder that holds only the book (the PDF and its maps). For a trial
against a gold, nothing in it may come from the gold: a third trial run read a
checklist of the gold's door pairs that lay next to the book, and had to be
redone (2026-11-16).

## What it leaves in `ingest/<book_id>/`

- the stage files above, and `adventure.yaml` assembled from them
- `questions.md`: every question, the answer or the guess taken, and what was
  simplified because the engine cannot hold it yet
- `eval.md` when a gold conversion of the book exists
- `extract/` (the book's text and pictures): ignored by git

The adventure is done when `uv run --project ../dnd-game adventure-ingest
verify ingest/<book_id>` passes. To play it, move the folder next to the other
adventures in dnd-adventures, or start a campaign with `ingest/<book_id>` as
the adventure.
