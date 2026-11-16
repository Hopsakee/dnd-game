# Build Plan — Solo D&D Engine

A solo Dungeons & Dragons 5e game where an LLM tells the tale and deterministic Python owns all game state and rules. The long-term goal is to feed in a published adventure book, convert it to a structured format, and play it without a human dungeon master.

This document is the plan for an agentic coding system. Read it fully before starting. Build milestone by milestone, in order. A milestone counts as done only when its acceptance criteria are verified, not when the code is written.

Working project name: `solo_dm` (rename freely before the first commit).

---

## 1. Core principles

1. **Python owns the truth. The model never decides outcomes.** Every state change, dice roll, hit, miss, damage number, door state, inventory change and win condition is decided by deterministic Python.
2. **The LLM has two jobs only:**
   - **Interpreter:** turn the player's free-text action into a structured *intent* (JSON), which Python validates and resolves.
   - **Narrator:** describe the *outcome* that Python already decided, in the voice of a dungeon master.
3. **State changes only through events.** Turn resolution produces events (`DoorOpened`, `DamageDealt`, `ItemTaken`, …). A pure function applies each event to the state. The event log is the source of truth.
4. **Tabletop freedom via fallback.** Any action without a specific rule becomes an ability check: the interpreter proposes the ability and approach, Python sets the difficulty and rolls.
5. **Everything testable without a network.** Dice and the LLM are behind ports. Tests use seeded dice and a fake LLM.
6. **Start minimal, grow by evidence.** Only build rules the current adventures need. The turn log shows which mechanics to build next.
7. **Multiplayer-ready data from day one.** Up to 5 players (Jelle + 4) is a future goal. Multiplayer itself is built later, but the data model must not assume a single player: the state holds a party, every action has an actor, and turn order is a list of actors. Solo play is a party of one.

---

## 2. Decisions (locked)

| Topic | Decision |
|---|---|
| Ruleset | D&D 5e **SRD 5.2** (CC-BY-4.0, credit in README) |
| Rules in v1 | One pre-made character (level 1 Fighter), ability checks, attack rolls, damage, hit points, only the conditions the test adventure needs. No spellcasting, levelling, rests or party members yet. |
| Narration language | English (all data, code and prompts in English too) |
| Host | A Docker container, reachable from the phone only over Tailscale (a Tailscale sidecar container; no public hosting). Runs on the Mac mini under OrbStack; the same image moves unchanged to NixOS (planned for the Mac mini) or a server. Decided by Jelle 2026-11-14: Linux everywhere, and Tailscale rather than Caddy + Authelia because the app spends on a company Claude API key. Supersedes "runs locally on the Mac mini" (2026-11-10). |
| Development | Built by Claude Code in Jelle's box (container on the Mac mini), in a GitHub repo cloned with `ensure-repo`; changes land as PRs via `open-pr`. Where the game runs for phone play: see Host (decided at M6). |
| Model while building | **Claude Haiku 5.5** (`claude-haiku-5-5`) via the Anthropic API, for both interpreter and narrator. If narration reads flat, try Sonnet 5.5 for the narrator only: a settings change, judged in play. |
| Model fallback | If budget becomes a concern: Mistral (preferred) or a router such as OpenRouter. Switching must be a config change plus one adapter class. |
| Interface order | Terminal harness first (development + tests), web app as later milestone |
| Web framework | **FastHTML** (HTMX-based), mobile-first |
| Adventure storage | Plain text files (YAML) in git, validated by Pydantic models |
| Campaign storage | One **SQLite** file per campaign: event/turn log + state snapshots. Adventure is copied into it at campaign start (frozen copy). |
| Lore storage | Markdown files in git with tags; searched via SQLite **FTS5** keyword search. Embeddings only if keyword search visibly misses. |
| Maps v1 | Node map of discovered rooms and connections. Combat positioning abstract (melee / range). No grid. |
| Architecture | Two-layer core/infrastructure (ports & adapters), core split by domain, dependency rule enforced by import-linter |
| Multiplayer | Future goal: up to 5 players. v1 is solo, but party, `actor_id` and turn order are built in from M1 (see 3.4). Multiplayer features themselves come later (see 9). |
| Architecture guide | `solo-python-architecture-guide.md` applies for layering, ports, Pydantic-in-core and testing. Its deployment sections (Caddy, Authelia, Granian, `X-Forwarded-User`) do **not** apply: this app runs as one container behind a Tailscale sidecar, with no login of its own. |
| Character at 0 HP | v1: the character is **defeated** and the adventure is lost. No death saving throws, no unconscious state. Revisit when party members exist (someone could then stabilise you). |
| Monster behaviour | Decided by Python, never by the model. v1: a hostile creature attacks a random conscious party member in reach; it never flees. Richer tactics grow by evidence. |

---

## 3. Architecture

### 3.1 Two layers

- **Core** (`src/solo_dm/core/`): pure Python + Pydantic. Rules, game state, events, adventure schema, turn resolution, and abstract *ports*. **No** imports of SQLite, HTTP clients, LLM SDKs, FastHTML, file I/O or any other infrastructure.
- **Infrastructure** (`src/solo_dm/infrastructure/`): implements the ports. LLM adapters, SQLite campaign store, YAML adventure loader, FTS5 lore index, terminal UI, web app, settings loading.

Dependencies point inward only. Infrastructure imports core. Core never imports infrastructure.

**Enforce this automatically** with `import-linter` contracts, run by a pytest test, so `uv run pytest` covers it. A violation fails the build.

Pydantic is allowed and encouraged in core: the same models validate adventure YAML, define game state, and generate the JSON schema the interpreter must output. One source of truth; no duplicate schema files.

### 3.2 Directory layout

```
solo_dm/
├── BUILD_PLAN.md
├── README.md                 # incl. SRD 5.2 CC-BY-4.0 attribution
├── pyproject.toml            # uv-managed
├── settings.yaml             # model provider/name, paths, cost limits (no secrets)
├── .env.solo_dm              # API key, only outside the box — gitignored, filled in by Jelle
├── .importlinter
├── adventures/
│   ├── core_five_rooms/      # smoke-test adventure (always playable start→win)
│   └── scenarios/            # one tiny scenario per feature
├── lore/                     # markdown lore files with tags in front matter
├── srd/                      # SRD 5.2 data needed by the engine (monsters, items)
├── campaigns/                # SQLite campaign files — gitignored
├── evals/                    # ingestion evals and the repo's own test book (M8)
├── src/adventure_ingest/     # extract/check/assemble/verify/eval for M8; imports only solo_dm.core.adventure
├── plugins/adventure-converter/  # M8: the converter agent and its skills (Claude Code plugin)
├── src/solo_dm/
│   ├── core/
│   │   ├── rules/            # checks, attacks, damage, conditions, difficulty
│   │   ├── state/            # GameState models, events, apply_event()
│   │   ├── adventure/        # adventure schema (Pydantic), validation helpers
│   │   ├── turn/             # turn pipeline: intent → resolution → events
│   │   └── ports.py          # LLMPort, DicePort, CampaignStorePort, AdventureSourcePort, LorePort
│   ├── infrastructure/
│   │   ├── llm/              # anthropic_adapter.py, mistral_adapter.py (later), fake_llm.py
│   │   ├── dice/             # random_dice.py, seeded_dice.py
│   │   ├── persistence/      # sqlite_campaign_store.py
│   │   ├── adventures/       # yaml_adventure_source.py
│   │   ├── lore/             # fts_lore_index.py
│   │   ├── terminal/         # terminal_game.py
│   │   ├── web/              # FastHTML app (milestone 6)
│   │   └── settings.py       # loads settings.yaml + .env.solo_dm
│   └── composition_root.py   # wires adapters into core services
└── tests/
    ├── core/                 # fast unit tests, no I/O
    ├── infrastructure/       # adapter tests (SQLite in tmp dirs, etc.)
    ├── playthroughs/         # scripted playthroughs per adventure/scenario
    └── live/                 # real-model tests, only run on request
```

File names state their purpose (`rules_combat.py`, not `utils.py`).

### 3.3 Ports (defined in core)

| Port | Purpose | Adapters |
|---|---|---|
| `LLMPort` | `interpret(player_input, scene_context) -> Intent` and `narrate(outcome, scene_context) -> str` | `AnthropicLLM`, `FakeLLM` (scripted), later `MistralLLM` / router |
| `DicePort` | `roll(expression) -> RollResult` | `RandomDice`, `SeededDice` |
| `CampaignStorePort` | append events, save/load snapshots, list turns, rewind | `SQLiteCampaignStore`, in-memory fake for tests |
| `AdventureSourcePort` | load and validate an adventure by id | `YamlAdventureSource` |
| `LorePort` | `search(query, tags) -> list[LoreSnippet]` | `FtsLoreIndex`, in-memory fake |

### 3.4 Event-based state

- `GameState` is a Pydantic model: **party** (characters keyed by `character_id`, each with HP, abilities, inventory, conditions, controlling player id), party location, discovered locations, per-entity state (monster HP, alive/dead, attitude), door/lock states, quest flags, turn number, and **turn order** (ordered list of actor ids, used for combat initiative).
- Never write code that assumes exactly one character (no `state.character`, no "the player"). Solo play is a party of one.
- Every event carries an `actor_id` (a character or a creature) when an actor caused it.
- Every change is an `Event` subclass with a type and payload. Examples: `MovedTo`, `LocationDiscovered`, `DoorUnlocked`, `DoorOpened`, `ItemTaken`, `AttackRolled`, `DamageDealt`, `CreatureDied`, `CheckRolled`, `AttitudeChanged`, `QuestFlagSet`, `AdventureWon`.
- `apply_event(state, event) -> GameState` is a pure function. It never rolls dice and never calls anything outside core. State models are frozen (`model_config = ConfigDict(frozen=True)`); `apply_event` returns a new state via `model_copy(update=...)`. No mutating methods on state models.
- `initial_state(adventure, party) -> GameState` builds turn-0 state from the adventure data. Replay always starts here.
- Every event carries a `schema_version` (int, starts at 1). Cheap now; it is what makes changing the event format possible once real campaigns exist.
- Rolls are recorded *inside* events (e.g. `AttackRolled` carries the d20 result and modifiers), so replaying the log reproduces the exact game without dice.
- Snapshots are a cache. Invariant, covered by a test: replaying all events from the initial state equals the latest snapshot.

### 3.5 The turn pipeline

```
player input (always tagged with the acting character_id — set by Python
              from the session, never chosen by the model)
  │
  ├─ built-in command? (inv, hp, look, map, help, save, quit)
  │     → answered directly by Python, no model call
  │
  └─ otherwise
        1. Build scene context (current location, visible entities, exits,
           relevant state, lore snippets for tagged entities). Only what
           the party can perceive: undiscovered locations, hidden items and
           secret exits are left out, so neither the interpreter nor the
           narrator can leak or target them.
        2. LLMPort.interpret → Intent JSON
        3. Validate Intent against Pydantic schema
             - invalid → one retry with the validation error, then a
               clarifying question to the player (logged)
        4. Resolve in core: check legality against state and adventure,
           pick the rule (move / attack / take / use / open / talk / search /
           check),
           roll via DicePort, produce events
             - no specific rule → ability-check fallback
             - illegal action (e.g. walking through a locked door) → a
               "Blocked" outcome with a reason, no state change
        5. Apply events → new state
        6. If in combat: Python runs every creature turn that comes before
           the next party member in turn order (see 3.5.1), producing and
           applying more events
        7. Persist events + snapshot
        8. LLMPort.narrate(outcome of steps 4–6) → narration text
        9. Persist narration in the turn log
```

#### 3.5.1 Combat

- Combat starts when a hostile creature and the party share a location (or when someone attacks). Python rolls initiative for every combatant and stores the turn order in state (`CombatStarted` event).
- On a party member's turn, the player's input runs through the pipeline above. On a creature's turn, Python picks the action (see decision "Monster behaviour") and resolves it with the same rules code.
- One player turn plus the creature turns after it produce one narration call, not one per creature.
- Combat ends when no hostile creature is alive in the location, or the party leaves (`CombatEnded`). Fleeing gives no opportunity attacks in v1.
- Positioning stays abstract: a creature is in melee reach of everyone in its location.

### 3.6 Intent schema (starting point)

The interpreter returns one intent per turn. The acting character (`actor_id`) is attached by Python, not produced by the model.

- `action`: one of `move`, `attack`, `take`, `use_item`, `open`, `unlock`, `talk`, `ability_check`, `look`, `search`, `other`
- `target_id`: id of an entity/exit/item from the scene context (must exist; validated)
- `item_id`: optional
- `ability`: for `ability_check` — STR/DEX/CON/INT/WIS/CHA, optional skill
- `approach`: short free-text description of how the player does it (for narration and logging only; never affects mechanics)
- `task_category`: for `ability_check` only — one of a fixed list (e.g. `trivial`, `easy`, `medium`, `hard`) that Python maps to a DC (see 3.7)
- `lore_query`: optional short query (see 3.8)
- `confidence`: low / medium / high. **Low** → Python asks the player to confirm ("Do you mean: …?") instead of resolving. Medium and high resolve. If this rule proves useless in the turn log, drop the field.

The scene context sent to the interpreter lists valid ids, so the model picks from them instead of inventing names.

**Compound input** ("I grab the key and run north"): v1 resolves only the first action and tells the player the rest was not done. The turn is tagged `compound=true` in the log, so its frequency decides whether multi-intent turns are worth building.

### 3.7 Ability-check fallback

- Interpreter proposes ability (+ optional skill) and approach.
- **Python sets the DC** from data: base difficulty by the interpreter's `task_category` (a fixed table in core; the model picks a category, never a number), adjusted by entity state (e.g. creature attitude hostile / indifferent / friendly per SRD 5.2 influence rules).
- Python rolls, decides success/failure, and produces events from a small, fixed set of fallback consequences defined in the adventure data (e.g. `on_success: set_flag goblin_allied`). If the adventure defines no consequence, success/failure is narrated with no state change.
- Every fallback turn is tagged `fallback=true` in the turn log, so it's easy to query which mechanics to build properly next.

### 3.8 Lore

- Markdown files in `lore/`, one per topic, with front matter: `tags: [goblin, faction, ...]`.
- Indexed into SQLite FTS5 at startup (rebuild when files change).
- Two retrieval paths:
  1. **Automatic:** Python pulls lore for tags attached to entities in the current scene.
  2. **On request:** the interpreter may request a lore lookup when the player mentions something unexpected (a `lore_query` field in the intent, resolved before narration).
- Lore is **context only**. It shapes interpretation and narration; it never changes outcomes. Anything mechanical (attitude, HP, DC modifiers) lives in adventure data or state.

### 3.9 LLM adapter and cost control

- Provider, model name, base URL, and max tokens and effort per role (interpreter, narrator) come from `settings.yaml`. No temperature: Haiku 5.5 refuses a non-default one (changed in M3, 2026-11-12).
- **Where the key lives.** Development runs in Jelle's box, which may hold no third-party key. There the adapter calls the Anthropic API through the host's credential broker, which adds the key; `settings.yaml` sets the broker's base URL and no key. Outside the box (e.g. on the Mac mini) the same adapter calls `api.anthropic.com` directly with the key from `.env.solo_dm`. One adapter, two settings; no code path differs.
- Keep prompts provider-neutral; validate structured output with our own Pydantic schema rather than relying on provider-specific features.
- Log every call to a local file: timestamp, role (interpreter/narrator), model, input tokens, output tokens, estimated cost.
- `uv run solo-dm cost` prints spend per day and per campaign.
- Optional hard limit in settings: refuse new model calls above a daily cost cap.

**Known risk, not solved up front:** the narrator may invent state ("the goblin flees", "you find a second key"). The narrator gets only the decided outcome and perceivable facts, which limits this. Jelle flags bad narrations with a built-in `flag <note>` command (stored on the turn); build an automated check only if flags show a pattern.

---

## 4. Data formats

### 4.1 Adventure (YAML)

An adventure is a folder with YAML files, validated by Pydantic models in `core/adventure/`. Starting shape (refine while building milestone 2):

```yaml
id: core_five_rooms
title: The Amulet of the Sunken Shrine
start_location: entrance
win_condition:
  flag: amulet_retrieved

locations:
  - id: entrance
    name: Mossy Entrance
    description: >
      Key facts the narrator must include: damp stone stairs lead down,
      a rusted gate stands open to the north.
    exits:
      - id: entrance_to_hall
        to: hall
        direction: north
    entities: []
    items: []
    tags: [shrine]

  - id: hall
    # ...

entities:
  - id: goblin_scout
    srd_ref: goblin              # stats from srd/
    location: guard_room
    attitude: hostile
    tags: [goblin]

items:
  - id: iron_key
    name: Iron Key
    location: hall
  - id: sunken_amulet
    name: Sunken Amulet
    location: shrine
    on_take:
      set_flag: amulet_retrieved

locks:
  - exit: hall_to_shrine
    locked: true
    key: iron_key
    pick_dc: 15
```

Hidden things and loot (M2.5):

```yaml
items:
  - {id: iron_key, name: Iron Key, carried_by: goblin_scout}      # on the body
  - {id: silver_chalice, name: Silver Chalice, location: storeroom,
     hidden: {dc: 15}}
locations:
  - id: storeroom
    exits:
      - {id: storeroom_to_crypt, to: crypt, direction: down, hidden: {dc: 13}}
```

- An item has exactly one of `location` and `carried_by` (an entity id). A carried item cannot be hidden.
- `hidden: {dc: N}` on an item or exit keeps it out of the scene context until found:
  - **Passive:** on entering a location (and at the start), the party member with the best passive Perception (10 + WIS modifier + proficiency bonus if proficient in Perception) finds every hidden thing there whose DC it meets. No roll.
  - **Active:** the `search` action without a target is one Wisdom (Perception) check; it finds every unfound hidden thing in the location whose DC the total meets. It can be retried, each try a turn. With nothing hidden it still rolls, so a search never reveals that a room is empty.
  - **Bodies:** `search` targeting a dead creature needs no roll; what it carried now lies in its location. A living creature cannot be searched.
- Events: `HiddenFound` (target, method `passive` or `search`), `BodySearched` (target, item ids).

Rule: every id is unique within the adventure, and every reference (exit target, key, location, carried_by) must resolve. The loader validates this and fails loudly.

### 4.2 Campaign SQLite schema (starting point)

- `campaign` — id, adventure id, created at, party snapshot at start
- `players` — player id, display name (one row for solo play)
- `adventure_copy` — frozen adventure data (JSON) copied in at campaign start
- `turns` — turn number, timestamp, actor id, player id, player input, intent JSON, validation result, fallback flag, compound flag, narration text, model call ids, player flag note, superseded marker (rewind)
- `events` — turn number, sequence, event type, actor id, payload JSON
- `snapshots` — turn number, state JSON

Writes for one turn happen in a single transaction.

---

## 5. Interfaces

### 5.1 Terminal harness (milestone 2)

- Line-based: narration scrolls, input below. Formatting with Rich.
- Built-in commands answered by Python without a model call: `inv`, `hp`, `look`, `map` (text list of discovered rooms/connections), `flag <note>` (mark the last turn as wrong, see 3.9), `help`, `save`, `quit`.
- Works well over SSH from a phone (short lines, no full-screen layout).

### 5.2 Web app (milestone 6)

- FastHTML + HTMX in a Docker container (see Host), reached over Tailscale. No separate auth layer; Tailscale is the perimeter.
- Mobile-first layout: narration stream, input box, quick-action buttons for common actions and built-in commands.
- Character sheet view, inventory view, node map (discovered rooms and connections, current location highlighted).
- Landing page with a menu linking to every screen (campaigns, play, character, map, cost log).
- The web app is a thin adapter: it calls the same core services as the terminal harness. No game logic in route handlers.

---

## 6. Testing strategy

Three levels:

1. **Unit tests (core):** rules, `apply_event`, turn resolution, DC calculation, adventure validation. Seeded dice. No I/O. Milliseconds.
2. **Scripted playthroughs:** run a full adventure through the terminal harness using `FakeLLM` (scripted intents, placeholder narration) and `SeededDice`. Assert on the final state and key events. Free and fast.
3. **Live tests:** a small set against the real model (Haiku), checking that typical player inputs produce valid intents. Run only via `uv run pytest -m live`, never automatically.

Rules:

- Levels 1 and 2 must pass before any task is marked done.
- **The core five-room adventure must always play from start to win.** It's the smoke test.
- **No new mechanic without a test scenario** in `adventures/scenarios/` that exercises it, with its own scripted playthrough. Once stable, a feature may also be woven into the core adventure, but its scenario stays.
- Event-replay invariant test: replaying events reproduces the latest snapshot.
- Import-linter contracts run with the tests.
- A test checks that no `.env*` file is tracked by git.
- Multiplayer-readiness tests: core rules and turn resolution also run with a party of two characters (both controlled by one test player), and combat turn order works with multiple party members and monsters.

---

## 7. Conventions

- **uv** for dependencies and running (`uv run`); never global `pip install`.
- **pytest** for tests.
- No task runner. Commands: `uv run pytest` (unit, playthroughs, import-linter), `uv run pytest -m live` (real model; deselected by default), `uv run solo-dm play`, `uv run solo-dm web`, `uv run solo-dm cost`, `uv run ruff check`.
- Settings in `settings.yaml`. No API key is ever in the repo or in the box (see 3.9). The code reads an optional key from `.env.solo_dm` (gitignored) only for running outside the box; Jelle fills it in himself.
- One source of truth: no value defined in two places that must match.
- File and module names state their purpose.
- Code, comments, data and prompts in English.
- Fix recurring bug classes at the source, not per instance.

---

## 8. Milestones

Each milestone ends with tests passing and something Jelle can actually try. Stop after each milestone and report: what was built, how to try it, what was verified, and open questions.

### M1 — Core skeleton
- Project setup: uv, pytest, a `solo-dm` console script (`[project.scripts]`), import-linter contracts, settings loading, `.env` handling.
- Pydantic models: `GameState` with a party (characters keyed by id) and turn order, `Event` types with `actor_id`, `apply_event`.
- `DicePort` with `RandomDice` and `SeededDice`.
- Minimal rules: ability checks, attack rolls vs AC, damage, HP, death of creatures, the pre-made level 1 Fighter.
- SRD 5.2 data for the creatures/items M2 needs.

- Combat round: initiative, creature turns, combat start/end (3.5.1).

**Done when:** unit tests cover checks, attacks, damage, a full combat (party wins and party loses) and event application, including with a party of two; import-linter passes; `uv run pytest` is green.

### M2 — Five-room adventure + terminal harness
- Adventure schema and YAML loader with reference validation.
- `core_five_rooms`: five rooms, one locked door with a key (also pickable), one monster, one treasure, win condition: retrieve the amulet.
- Turn pipeline with `FakeLLM`.
- Terminal harness with built-in commands.
- Scripted playthrough from start to win, plus at least one losing path (character dies).

**Done when:** `uv run solo-dm play` runs the adventure with the fake model; the scripted playthroughs pass.

### M2.5 — Hidden things and searching
Added 2026-11-11 from Jelle's first play test ("I immediately see everything in a room; I cannot search a dead goblin"). Before M3, because M3's prompts are written against the scene context, and before M4, because it adds event types.
- Adventure schema: `hidden: {dc}` on items and exits; `carried_by` on items (4.1).
- Passive Perception on entering a location and at the start; the `search` action for a location or a dead creature (4.1).
- Scene context leaves out unfound hidden things and carried items; tested for both interpreter and narrator input.
- `core_five_rooms`: the iron key is on the goblin; the silver chalice is hidden (DC 15, above the Fighter's passive 13); a tarnished ring is found passively (DC 11). Picking the lock stays as the other way through.
- `FakeLLM`: `search`, `search goblin`, `search the body`.

**Done when:** the playthroughs (win via the goblin's body, the hidden-things route) and the scene-context test pass; `uv run solo-dm play` lets Jelle search the room and the goblin.

Out of scope: traps, secret-door mechanisms, hidden creatures and Stealth, time cost of searching, a separate Investigation rule.

### M3 — Real model
- `AnthropicLLM` adapter (Haiku) for interpreter and narrator; prompts in their own files.
- Intent validation with one retry, then a clarifying question.
- Ability-check fallback with Python-set DC.
- Narrator prompt: never state the DC of a search (Perception) check; it would tell whether anything is hidden (M2.5).
- Cost logging and `uv run solo-dm cost`.
- Live tests (`uv run pytest -m live`).

**Done when:** Jelle can play `core_five_rooms` end to end with Haiku in the terminal; cost per session is visible; live tests pass.

### M4 — Persistence
- `SQLiteCampaignStore`: campaign creation (frozen adventure copy), events, turns, snapshots.
- Save, load, list campaigns, rewind to a turn. Rewind is **non-destructive**: later turns are marked superseded (a `branch` / `superseded_at` column), never deleted, so a rewound campaign can still be inspected.
- Event-replay invariant test.
- A query helper to list fallback turns and rejected intents.

**Done when:** a campaign can be stopped and resumed; rewinding works; the replay invariant holds.

### M5 — Lore
- `lore/` markdown files with tags; FTS5 index.
- Automatic lore for tagged scene entities; interpreter-requested lookups.
- A few lore files for the test adventure (e.g. goblins, the shrine).

**Done when:** lore appears in the scene context for tagged entities (verified by test), and narration with lore can be tried in `uv run solo-dm play`.

### M6 — Web app
- FastHTML app over the same core services.
- Landing page with menu; campaign list; play screen; character sheet; inventory; node map; cost view.
- Mobile-first layout, verified on phone width.

**Done when:** Jelle can play a campaign from his phone over Tailscale, including resuming a campaign started in the terminal.

### M7 — Engine for Revenge of Azzinax, and its gold adventure
Planned 2026-11-14 with Jelle. Ingestion (M8) needs a hand-verified target to measure against, and that target must be playable. So M7 grows the engine by what Azzinax needs, and Azzinax is converted by hand into the gold adventure.

The engine learns (all tested through the turn pipeline, as before):
- **Saving throws**: a d20 plus ability modifier (plus proficiency where the character has it) against a DC. Python rolls; the model never picks the DC.
- **Hazards and traps**: a hazard in a location. It can be noticed by passive Perception, or found by searching (as hidden things are now), and it triggers when entered unnoticed: a save against a DC, with damage on a failure. For the falling rocks, the spike pit and the poison mushrooms.
- **Stuck doors**: an exit forced open with a Strength (Athletics) check against a DC, next to locks with a key or a pick DC.
- **Using an item to open something**: using an item at a place sets a flag, and locks can open on a flag. For the coin in the fountain, which opens all the doors of room 3; the coin is used up.
- **A healing potion**: an item with an effect (heal 2d4+2), used up when drunk.
- **A rescue at 0 HP**: an adventure may name a guardian that, once per adventure, brings the hero back to full HP instead of defeat. For Spiritus Magehunter, and an answer to the harsh solo fights of the M6 play test.

The conversion simplifies, for now: ranged attacks become melee; money becomes plain items; rests are dropped; the magic items keep their description but have no effect; the mushrooms' disadvantage is left out (no conditions yet); Spiritus's advice is ordinary talk, and he does not fight.

The gold adventure: `revenge_of_azzinax/` in the private repo `dnd-adventures` (see "Where adventures live" below). Drafted from the book and the map, then checked by Jelle against the book. The four homebrew stat blocks and the baboons and crawling claws go in with it, outside `srd/` where they are not SRD. The repo gets a scenario per new mechanic, as for earlier milestones.

**Done when:** Jelle plays the gold Azzinax adventure to the end on his phone, and each new mechanic has a scenario with a scripted playthrough.

**After the first phone play test (Jelle, 2026-11-14).** Fixed in M7: freeing Min-soo could not be won (the check fired only for DEX and the interpreter could not see it; now a challenge with a goal), the narrator's memory (last three turns; creature activity out of room descriptions), talking to the guardian, the Runt joining the fight (`group`), the hero's own purse, leaked planning (`<narration>` tags), no initiative in the narration. Deferred by Jelle until after M7, built in Goal E (2026-11-15):
- Money as amounts (8 sp, spend 1) instead of purses as items. *Built:* `Coins` per denomination on the character (the Fighter starts with 18 gp); an item with `coins` is money, taken into the purse; a location's `uses` can `pay` coins, cheapest first; the party's money is the pack item `coins`. Scenario `coin_purse`.
- Choosing a weapon (wield a carried one); weapon stats for found weapons, and the Cursed Warhammer's -1d4. *Built:* an item with `weapon` stats joins the weapons when taken; the `wield` action; `damage_penalty` dice are subtracted from each hit. Wielding takes the turn in a fight. Scenario `cursed_hammer`.
- Doors on the map; the book's own player map, revealed as the party explores (needs room outlines in `map.yaml`). *Built:* `door: true` on exits, a door mark on the node map (filled while shut); `map.yaml` takes `player_image`, `cell_px` and `cells` per location, and the web map shows the image clipped to the discovered locations and the openings out of them, the node map folded under it. The clip is client-side: the image address shows the whole map (no image library in the box to crop it). Scenario `player_map`, image drawn by `scripts/draw_player_map_scenario.py`.
- Still open from M7: hidden creatures (the Runt in the shadows, the goblin behind the statue), checks with preconditions or costs (the platform after Azzinax, the fall, DC 5 after a failure), the mushrooms' condition.

**Where adventures live (Jelle, 2026-11-14): game and adventure data in separate repos.**
- `dnd-game` (this repo): the engine, web app, ingestion application and tests, plus only the data the tests check the engine with: `core_five_rooms`, the scenarios, their lore, and M8's own small test book.
- `Hopsakee/dnd-adventures` (private, no code): converted books with their gold versions, lore that belongs to a book, and the ingest work folders with the manual model answers. Changed through PRs like this repo.
- The source books (PDFs, maps, zips) stay on Drive: large, unchanging, backed up to the NAS. In the box: `~/transport/dndgame/`.
- The game reads adventures from both places: `settings.yaml` gets a second adventures path, and `compose.yaml` mounts a clone of `dnd-adventures` read-only, so no image contains a copyrighted adventure.
- Supersedes "a gitignored `adventures/private/`" (2026-11-13).

### M8 — Ingestion: a converter agent in Claude Code
Decided by Jelle 2026-11-14 (supersedes the same day's "separate application" with model steps run by hand or through the API). Converting a book is judgement, not extraction: what is a challenge and what is its goal, which door seals from which side, who belongs to which group. Those were the Azzinax errors, and a stronger model alone would not have caught them; a question to Jelle would. Jelle converts at most four books a year, so half an hour of steering per book is cheaper than a pipeline, and a flaw is fixed by adding a rule or example to one skill. It runs on his subscription (Fable or Opus), in Claude Code, later Cowork.

- **An agent, run as the session itself.** `plugins/adventure-converter/` in this repo is a Claude Code plugin: one agent (`adventure-converter`) plus one skill per domain. Jelle starts Claude Code *as* the agent (`claude --agent …`; the exact command, with the plugin, is verified and written in the README in M8), so it can ask him whenever it is unsure. A sub-agent cannot ask the user anything, so sub-agents are only for heavy, self-contained reading (the map image, a page of stat blocks), and return a draft file plus a list of questions the agent puts to Jelle.
- **The agent's context:** the adventure schema (generated from the Pydantic models, never retyped), the SRD 5.2 monsters and items in `srd/`, the map convention below, and the gold Azzinax only as a description of what good looks like (no book text in this repo).
- **One skill per domain the engine can hold today:**
  | Skill | Writes |
  |---|---|
  | `map` | `map.yaml`: rooms, corridors, openings and what each meets (the convention below), then the locations and exits (with `door: true` where the opening is a door); for a book with a player map also `player_image`, `cell_px` and each location's `cells` (Goal E, see `AdventureMap` in `core/adventure/map_schema.py`) |
  | `challenges` | every check as a challenge: id, goal, ability, skill, DC, what success sets |
  | `creatures` | SRD reference or own stat block, place, attitude, group, activity, the check that talks one round |
  | `items-locks-hazards` | items and their uses, locks on both sides of a door, hazards, the win flag |
  Domains the engine cannot hold yet are listed below as later work; a skill never extracts what no engine field reads.
- **Stage files in `dnd-adventures/ingest/<book>/`,** one per skill plus `questions.md` (every question the agent asked and Jelle's answer). A stage can be reviewed, corrected or redone the next day without the rest. `questions.md` is where skill improvements come from: a question asked for every book is a rule the skill lacks.
- **The code stays code,** in `src/adventure_ingest/` (command `uv run adventure-ingest`), called by the agent through the shell. It may import the engine's adventure schema (`solo_dm.core.adventure` and the models it uses) and nothing else from `solo_dm`; `solo_dm` never imports it; the architecture test enforces both.
  1. `extract`: PDF (or Fantasy Grounds XML) to text and page images, plus a report of pages that are images with little text (Azzinax page 6). `pymupdf4llm`.
  2. `check <stage>`: validates one stage file at once, e.g. every opening in `map.yaml` has a partner that names it back.
  3. `assemble`: the stage files into one `adventure.yaml`, validated by the engine's schema.
  4. `verify`, **the hard gate**: the agent is not done until it passes. Every location is reachable; no key is behind its own lock; a locked door is locked on both sides; every id referred to exists; the win flag can be set; every monster has a stat block; every obstacle can be passed by the hero's abilities; every flag the win or a lock depends on is set by a challenge, an item or a use, never by a roll the model must guess (Azzinax play test, 2026-11-14).
- **Evals**, `uv run adventure-ingest eval <book>`: a conversion against the gold adventure, field by field (locations, links, monsters and where they are, items, locks, checks, hazards, the goal), as precision and recall per field. They tell whether a change to a skill made conversions better or worse. Every in-game error traced back to conversion becomes an eval case or a `verify` rule.
- **Copyright:** the plugin and its skills hold no book text; examples come from the repo's own small test book (an original adventure, PDF plus map image, plus its gold, in `evals/`). Gold adventures of bought books live only in `dnd-adventures`. `pytest` covers the code (`extract`, `check`, `assemble`, `verify`, `eval`) on the own test book; the agent itself is tested by a conversion and its eval report, not in `pytest`.
- SRD 5.2 versus 2014 stat-block layouts are handled in the `creatures` skill.

**The map step's convention (Jelle, 2026-11-14).** The `map` skill reads the map into a `map.yaml` of named openings; the gold one is `dnd-adventures/revenge_of_azzinax/map.yaml`, whose header carries the full rules.
- Rooms keep the book's number. A room's openings are lettered clockwise from the west end of the north wall: 5a, 5b, … Every opening says which opening it meets (5d = 3b), so a link is checked from both sides, and an opening without a partner is an error `check map` catches.
- Corridors are locations of their own, cut at every junction and numbered C1, C2, … in reading order (north first, then west); their openings are lettered the same way. The map's small letters (a, c, e, …) are features that lie in a corridor, not its name.
- **Every corridor stays a location, also an empty one.** Jelle's reasons: folding empty corridors away needs a check that a corridor is truly empty, and that check can fail; if only corridors with something in them exist, every corridor gives away that something is there; and distance is a game mechanic, e.g. what can be heard from room 9 depends on whether room 2 is next door or 18 m of corridor away. Supersedes the M7 draft of the gold Azzinax, which folded plain corridors into exits.
- An exit's id is its opening's name, and its direction is the wall it is in (two on one wall: the one near a corner takes that corner's diagonal). A corridor's directions point towards each end and are unique within the corridor; those are chosen by hand, so `check` only tests uniqueness.
- A door is two exits, one per side; the engine opens both when one is forced, unlocked or opened by a mechanism (`Adventure.other_side`, found 2026-11-14 while redoing Azzinax).
- Open question: a long corridor can hold features far apart (Azzinax C7: the crater near room 3, the spike pit 100 m on). The engine triggers a corridor's hazard on entering it, from either end. Cut long corridors at features too, or give hazards a position, when a play test shows it matters.

**Done when:** a trial conversion of Azzinax by the agent in the box (questions logged in `questions.md`, not answered) passes `verify` and has an `eval` report against the gold; the own test book's code tests pass in `pytest`; and Jelle has started the agent on his own machine and converted one book with it, ending on a passing `verify`.

**Built in the box (Goal D, 2026-11-15).**
- The own test book: `evals/millers_cellar/`, "The Miller's Cellar", an original adventure written for this. `build.py` draws the map from one layout (so the gold's cells and `at` match the picture), renders it and a stat block printed as a picture with Chromium, and builds `book/book.pdf` with pandoc/xelatex. `gold/` is the adventure a perfect conversion writes; `stages/` is the same gold split into stage files, which `assemble` turns back into exactly `gold/adventure.yaml` (a test). The skills point at `stages/` as their examples.
- `src/adventure_ingest/`, `uv run adventure-ingest extract | schema | check | assemble | verify | eval`. Stage files (`stages.py`, built from the engine's models): `map.yaml` and `locations.yaml` (skill map), `creatures.yaml` and `creatures/` (creatures), `items.yaml` (items-locks-hazards, also the win flag, hazards and uses), `challenges.yaml` (every check, `at` a place or a creature; the talk check too). No skill writes exits: `assemble` makes every opening an exit.
- `verify` walks from the start until nothing new opens (a key, picking, forcing, a flag set by a check, an item or a use; paying coins is assumed possible, the hero starts with 18 gp). It reports unreachable places, a key behind a lock it opens, a door locked on one side or differently on its two sides, an unreachable win, a creature without a stat block, a DC above 25 (a level-1 hero's natural 20 + 3 + 2), and exits that disagree with `map.yaml`. It passes on the gold Azzinax and the test book's gold.
- `eval` scores facts per field: places and exits by id (the map convention makes them comparable), the rest by what and where, never by the ids a converter chooses (items, flags, checks).
- `pymupdf4llm` is in the dependency group `ingest` (a default group); the Dockerfile exports with `--no-default-groups`, so the game's image stays without it.
- The plugin `plugins/adventure-converter/`; start command verified with Claude Code 2.1.325 (`claude --plugin-dir … --agent adventure-converter:adventure-converter`, the plugin prefix is needed), see its README.

**Findings (2026-11-15).**
- `verify` on the engine's own scenarios: `core_five_rooms`, `coin_purse`, `fountain_and_potion`, `locked_door` and `stuck_door` lock only the side the hero comes from. Harmless there (the far side is reached only through that door) and they are engine fixtures, not conversions, so the rule stays strict and the scenarios stay as they are.
- **Trial conversion of Azzinax** (`dnd-adventures/ingest/revenge_of_azzinax/`): headless, `claude -p` with the plugin and agent, Opus 5.5, about 8 minutes, 70 turns, $2.35 at list price. All checks and `verify` pass. Eval against the gold: recall 1.00 on every field except items (0.88: the book lets Hye-young pay with the potion *or* 8 sp, and the gold has both) and map openings (0.93: the off-map openings lettered the other way round). 12 questions with their guesses in `questions.md`. The transcript shows it never opened the gold or this plan before `eval`.
  - A first run scored the same, but the skills then held examples taken from the gold Azzinax (an activity, a challenge's id and goal, the fountain): hints at the answer key. The examples now come from the test book only, and the second run is the one kept. **Rule: examples in the skills come from `evals/`, never from a gold of a bought book.**
  - Lesson added to the `map` skill: off-map openings are lettered clockwise by direction, like a room's.
  - The headless start needs `--add-dir ../dnd-game <book folder>`; without it, listing those folders is refused (the first run worked around it).
  - An agent alone cannot test the eval's honesty: Azzinax is the only book with a gold, and the agent that built the skills had read it. Jelle's own conversion of a second book (The Goblin Cave) is the real test.
- **Jelle's answers to the trial's 12 questions (2026-11-16).** Eight guesses stand. The rest:
  - Three questions asked what the book answers (who starts the fight, Hye-young's payment, the platform); the engine could not hold the answer, so the agent asked instead. Rule now in the agent: the book is clear but the engine cannot hold it is not a question but an "Engine gaps" line (the section is renamed from "Simplified").
  - A door locked on one side is locked on both, without asking, unless the book explains why it opens from one side only. Now in `items-locks-hazards`.
  - The win is bringing Min-soo home (C): that is what Hye-young asked, and the reward is paid there. Rule now in the agent: the win is where the hook ends. The gold sets the win on the platform; it changes when the engine can hold "back home after freeing him".
  - The catwalk chest is not hidden but out of sight: one chest holding the agate and 7 gp, in plain view once the hero climbs the rope (DC 10 Athletics). Jelle's suggestion: the catwalk as a place of its own, reached by the rope. Rules now in `items-locks-hazards` (out of sight is not `hidden`; a container is one thing).
  - The mushroom gas: do what the book says, so the engine needs advantage and disadvantage; never invent damage. The platform: DC 10 Acrobatics, a 10 ft fall on failure, DC 5 for every retry, as the book has it.
  - On the whole "Simplified" list: "possible, but in the final game we really don't want to need this." Simplifications are engine work to do, not a state to accept.
- **Engine gaps from the trial.** The four Jelle named go in M8.5 (below); the rest wait until after M9: containers (the catwalk chest holding the agate and 7 gp); hidden creatures and surprise (the Runt, the goblin behind the statue); ranged attacks, Nimble Escape, Pack Tactics; magic item effects (Ring of Safety +1 saves); an ally who advises, gives a short rest and fights (Spiritus); short and long rests; creatures that arrive on a trigger (room 1's extra goblins).
- Not built: reading Fantasy Grounds XML in `extract` (no book in the queue needs it before Skyhorn).
- `claude plugin validate --strict` passes; the plugin-directory notes (no LICENSE, no icon) matter only for publishing it.

**After M8: domains the engine cannot hold yet (Jelle, 2026-11-14).** Each needs the engine first (a schema field, the narrator or rules using it, a test), then its converter skill. Suggested order:
1. **Story and style:** the arc, tone and setting, as a brief the narrator writes in. Changes how every game feels.
2. **Creature goals:** what a monster or NPC wants, so it acts convincingly (talk, flee, bargain).
3. **NPCs:** who they are, what they know and will tell.
4. **Images:** pictures from the book or generated, shown at the right moment.

### M8.5 — The book as written: four engine gaps
Decided by Jelle 2026-11-16: before M9, the engine gets the four gaps he named in his answers to the Azzinax trial, so the gold Azzinax follows the book there instead of simplifying it ("in the final game we really don't want to need this"). The other gaps wait until after M9 (M8 findings). Each one is built as in M7: the schema field, the rules using it, a scenario with a scripted playthrough.

**1. Advantage and disadvantage, and a condition that gives it** (the mushroom gas).
- Every d20 (attack, check, save) goes through one roll function: with advantage or disadvantage it rolls two and keeps the higher or the lower; both at once cancel (SRD 5.2). The roll event carries both dice, so the log and the narration show them.
- `Character.conditions` (in the model, unused so far) gets its events, ConditionGained and ConditionEnded. The first condition: disadvantage on the next attack roll, ability check or save, used up by that roll.
- `Hazard`: damage becomes optional, and a failed save can give a condition. A hazard has damage, a condition, or both.
- Not now: advantage from the situation (Pack Tactics, an unseen attacker). The roll function takes it once something gives it.

**2. A challenge as the book sets it** (the room 4 platform).
- `CheckConsequence` gets `requires` (point 3), `on_failure` damage (a 10 ft fall is 1d6 bludgeoning, SRD 5.2) and `retry_dc`: the DC for every attempt after a failed one. A failed attempt is an event, so the next attempt knows it.
- A challenge whose `requires` does not hold is not open: the models do not see its goal, and an attempt is blocked with the reason.
- `on_success` can move the hero (`move_to`): jumping onto the platform puts him on it, rather than opening a way he must then still take.

**3. One guard, `requires`, used in four places** (the win at home, Hye-young's offers).
- `requires: {flags, not_flags, defeated}`: flags set, flags not set, creatures dead. One small model, so the converter learns one thing.
- On a challenge (the platform: Azzinax defeated); on an item, which is only there while its guard holds (the potion unless the hero pressed for payment, the 8 sp unless he took the potion); on a use; and on a new location field `on_enter: {requires, set_flag}`: arriving sets a flag. Back in the village with Min-soo freed sets the win.
- Money after the win changes nothing in play, so the 15 sp (unless the 8 sp were taken) belong in the ending the narrator tells, not in an item.
- `verify` reads the guards: a flag or item counts as reachable only when its guard can hold. `not_flags` are a choice the player makes, so verify takes them as holdable.

**4. A place inside a room** (the catwalk in room 8, the platform in room 4).
- `Location.within: <room>`: a part of a room the hero must first reach. It is in `locations.yaml`, not in `map.yaml`'s openings; on the player map it shows the room's cells.
- Its way in and out is an exit pair from `locations.yaml`, as hidden exits are now; a challenge gets the hero there (`move_to`) and its flag opens the pair (`opens_on_flag`), so he can come back down and go up again.
- So the catwalk chest is in plain view on the catwalk, not hidden; and freeing Min-soo is being on the platform (`on_enter`). Containers stay after M9: the chest's contents are items described as in it.

**Converter, test book and gold.**
- The stage schemas follow from the engine models as before; `check`, `assemble`, `verify` and `eval` learn `requires`, `on_enter`, `within`, `move_to`, `on_failure`, `retry_dc` and conditions.
- The Miller's Cellar gets one example of each (skill examples come only from `evals/`): a loft reached by a ladder that can drop you, dust that gives disadvantage, a reward with a guard, a win on coming back. The skills drop these four from their "Engine gaps" and say how to write them.
- The gold Azzinax (a dnd-adventures PR): the win at home, Hye-young's offers guarded, the platform and the catwalk as places within their rooms, the gas as a hazard with a condition.

**Done when:** each of the four has a scenario with a scripted playthrough; the gold Azzinax and the test book pass `verify` with them; a new headless trial conversion of Azzinax passes `verify`, scores at least the first trial's recall, and asks nothing the book answers; and Jelle plays the new gold through the platform and back to the village on his phone.

**Built in the box (2026-11-16).**
- Engine: `rules_d20.roll_d20` for every character's d20; the roll events carry `d20_rolls`, `roll_mode` and the condition they use up (`ends_condition`). Condition `disadvantage_on_next_roll`, event ConditionGained; a hazard has damage, a condition or both. `Requires` on challenges, items, uses and `on_enter`; `retry_dc`, `on_failure`, `on_success.move_to`, event ChallengeFailed (written only when a retry DC needs it); `Location.within`, and the player map shows the room there. The narrator prompt tells conditions and falls in the fiction, never naming them (live test).
- Scenarios with scripted playthroughs: `spore_gas`, `ledge_leap`, `two_offers`, `rope_and_catwalk`.
- adventure-ingest: `locations.yaml` takes places inside a room (`within`, id `<room>_<name>`) and their `inner_exits` (id `<place>_<direction>`, the only exits not on the map); `items.yaml` takes `arrivals` (`{at, set_flag, requires}`), which assemble writes as `on_enter`. `check`, `verify` (guards, `move_to`, arrivals, the retry DC, inner exits off the map) and `eval` (the new facts) know them.
- The Miller's Cellar has one of each: flour dust, the loft up a rotten ladder, Wenna's potion or 5 sp, Grist talking only once the goblins are dead, the win on coming back to the yard. Its map now has a page of its own (the longer text had put 120 words on it, and `extract` rightly stopped calling it a picture page).
- The gold Azzinax (dnd-adventures PR): the gas, the platform and the catwalk as places inside their rooms, Hye-young's potion or purse, the win on bringing Min-soo home. `verify` passes.

**Findings (2026-11-16).**
- Before M8.5 a challenge's flag never opened a door locked on that flag: only uses did. The test book's millstone would not have opened the bolted door in play. A challenge now sets its flag the way a use does, so doors open, and the win follows.
- Not built as planned: "an attempt is blocked with the reason" while a requirement fails. The models do not see a goal that is not open, so they cannot aim at it; an attempt is an ordinary fallback roll that changes nothing (seen in the `ledge_leap` playthrough).
- **Trial conversion of Azzinax with the M8.5 skills** (headless, Opus, about 7 minutes, 58 turns, $2.21): all checks and `verify` pass; eval 1.00 precision and recall on all 12 fields. Before `eval` it read only the book, the test book's stages, the SRD and the schemas. 6 questions (was 12): three the book leaves open (the off-map places, the baboon and claw numbers, the stuck-door DCs) and three that only confirm what the book says (the platform needs only Azzinax, a failed rope climb costs nothing, reaching Min-soo frees him). Rule added to the agent: a guess that is just the book is a note, not a question; not yet tried in a run.
  - A run before it was thrown away: the book's folder given to `--add-dir` was `~/transport/dndgame/`, which also holds `azzinax_openings.md`, a checklist of the gold's door pairs, and the run read its first 20 lines. The plugin README now says the folder must hold only the book.
  - What a 1.00 does not cover: `eval` does not compare cells, `at`, directions, descriptions, attitudes, groups, the guardian, uses other than the win, or a guard's flags (only that an item has one). And the skills were written by a session that knew the gold; The Goblin Cave, with no gold anyone has read, stays the real test.
- One live test (key narrated as lock-picking) failed once and passed on its rerun and in the next full run: the model is not deterministic, and nothing in this milestone touches it.

### M9 — Scaling to one player (The Goblin Cave)
- An `adventure-ingest scale` stage: each encounter's difficulty for the party the book was written for, cut to one character's budget (fewer or weaker monsters), deterministically.
- The obstacle check of `verify` covers the skills a party shares (Arcana, Thieves' Tools).
- First check whether SRD 5.2 has the per-character XP budget table (see the scaling decision below).

**Done when:** The Goblin Cave, converted and scaled from a party of 5 to one level-1 Fighter, is playable to the end, and an eval checks the scaled encounters.

### Test books and findings for M7-M9

**Test books in order (Jelle, 2026-11-14).** Skyhorn needs too much engine to come first, so start small and change one thing at a time:

1. **Revenge of Azzinax** (Alexander Thomas): ingestion first. Written for one level-1 player, so no scaling at all.
2. **The Goblin Cave** (Bruno71): scaling next. Written for a party of 5 at level 1-3, with a monster set per level.
3. **Dead Ends: Grungus the Ghoulish** (lowerlevels.ca): later. For 3-5 level-1 players; a spellcasting boss, saving throws, a swamp.
4. Skyhorn Lighthouse (below): last.

All three are in `~/transport/dndgame/` in the box. Like Skyhorn, converted adventures stay out of git. The Goblin Cave says "Permission granted to print or photocopy this document for personal use only". The other two's licences are not checked.

**Scaling to one player: shrink the fights when converting (Jelle, 2026-11-14).** Of the three options considered, this one: the conversion computes each encounter's difficulty for the party the book was written for and cuts it to one character's budget (fewer or weaker monsters). It is deterministic, so evals can check it, and the adventure text stays as written. Not chosen for now: Python-run companions (keeps the encounters, more engine work, a step towards multiplayer) and a stronger hero (bends 5e). Scaling is more than combat: the conversion must also check that one Fighter can solve every obstacle (skills a party would share, such as Arcana or Thieves' Tools), alone or through the ability-check fallback. Open: whether SRD 5.2 contains the per-character XP budget table (the 2024 DMG has one); check before relying on it.

**Revenge of Azzinax: what extraction gave (2026-11-14, `pymupdf4llm`, 8 pages, 1,367 words).**
- Text: a hook (a village, an old woman, a kidnapped grandson), a forest encounter (2 baboons), and a dungeon guide table: 9 rooms and 8 corridor features (a, c, e, i, m, n, r, s). The goal is clear: defeat Azzinax in room 4 and free Min-soo.
- **The connections are only on the map.** Room entries say which wall and what kind of door, but mostly not where they lead (only "leads to room #5" and the like for a few). The graph comes from the map image (`Lair of Azzinax 01`, 1751×2251 PNG, grid). The gold standard is drawn by hand; automatic extraction from map images is a separate question.
- **The stat blocks are images.** Page 6 (Azzinax, Goblin Runt, Modified Goblin, Spiritus Magehunter) extracts as an empty heading. They need a vision model or hand entry. An eval case: the extracted text must not silently miss a page of stat blocks.
- Monsters: baboons and crawling claws (Monster Manual; whether they are in SRD 5.2 is not checked), plus four homebrew stat blocks.

**Engine gaps Azzinax exposes** (engine as of M6). What the engine gets and what the conversion simplifies away is decided in M7 above:
- Traps and hazards with saving throws (falling rocks DEX 15, poison mushrooms CON 15, a spike pit). The engine has no saving throws and no traps.
- Conditions: disadvantage on the next roll.
- Ranged attacks (shortbows, darts). Combat is melee only.
- Stuck doors to force (a STR check); the schema has locks with a key or a pick DC, not "stuck".
- A puzzle: a coin tossed into the fountain opens all doors of room 3. There is no currency, and "use this item here" does not unlock exits.
- An ally, Spiritus Magehunter: gives advice, restores the hero to full HP once at 0 HP, and fights in the final battle. Also an answer to the harsh solo fights seen in the M6 play test (one goblin fight in seven is lost, 2,000 runs).
- Consumables and rests: a healing potion (2d4+2); a short or long rest after the baboons.
- Magic items with an effect: Ring of Safety (+1 saving throws), Cursed Warhammer (-1d4 damage).
- Talking before a fight: Azzinax talks first; the Goblin Runt ambushes if the hero turns hostile.
- A check with a precondition and a cost: after Azzinax is dead, Acrobatics DC 10 to reach the platform, or fall 10 feet.
- Money as a reward (sp, gp, gems).
- Places outside the dungeon: the village and the forest path.

**First test book (Jelle, 2026-11-13): The Secrets of Skyhorn Lighthouse** (Arcane Library; 5th level, party of 4-5).
- Where: `~/transport/dndgame/1060290-The_Secrets_of_Skyhorn_Lighhouse_V8-1.zip` in the box (PDF, print-friendly PDF, maps, combat cards, a Fantasy Grounds `.mod`).
- Copyright: a purchased product. The converted adventure goes in the private `dnd-adventures` repo (2026-11-14; was: a gitignored `adventures/private/`); this repo holds code, evals and findings only.
- Sources, use both and compare: the PDF is the real path, read with `pymupdf4llm` from the wheel store (23 pages). The `.mod`'s `db.xml` is clean structured XML (22 story sections, ~6,400 words; 16 NPCs, 4 items, 8 treasure parcels, 8 battles) and shows what PDF extraction loses.
- First extraction eval case: the ligatures fl and fi come out as "2" ("2laps open", "the 2irst turn").
- Scenes: rumours in the harbour; a water elemental attacks the ship; the lighthouse under siege by eelfolk; the caves below (sharks, hostages, the summoning room); aftermath.
- Engine gaps it exposes (engine as of M5): a party of 4-5 at level 5; spells and magic items (Bead of Force, Dagger of Venom, Potion of Water Breathing, Bowl of Commanding Water Elementals); swimming, underwater combat and holding breath; morale (sharks flee below 15 HP); allied NPCs (the ship's crew, Lucien) and NPCs with goals to talk to; travel scenes by ship; non-SRD monsters (four eelfolk) with their own stat blocks; treasure parcels as loot; maps that exist only as images. Which of these the engine gets and which the conversion simplifies away is decided when Skyhorn's turn comes (after M9).

---

## 9. Out of scope for now

- Spellcasting, levelling, rests, multiple party members, companions.
- Grid maps and positional combat.
- Embedding-based (semantic) lore search.
- Reverse proxies, public hosting or separate auth. (Docker is in since M6: see Host.)
- Narration in languages other than English.
- **Multiplayer features** (planned later; data model already prepared):
  - Collecting out-of-combat input from several players into one turn (the main open design question; decide after solo play works).
  - Player identity and sessions in the web app; giving friends access (likely Tailscale machine sharing, still no public hosting).
  - Per-player views and private information (e.g. a note only one player sees).
  - Concurrent input handling (one process resolving one turn at a time; SQLite is sufficient).

---

## 10. How to work

- Build one milestone at a time, in order. Don't start the next one before the current one is verified.
- Within a milestone, write tests alongside the code. Prefer small commits with clear messages.
- If something in this plan turns out wrong or ambiguous while building, stop and describe the problem and options rather than silently deviating.
- Ask before anything irreversible (deleting data, rewriting git history, changing the event format after campaigns exist).

### 10.1 One agent or a team

**Default: one agent, one milestone at a time.** Use a team (parallel subagents) only when all three hold:

1. **The pieces are independent.** No piece changes a model, schema or file another piece reads. `GameState`, events and rules are shared by everything, so work on them is never split.
2. **Each piece can be briefed in a few lines** and checked on its own output (a test, a validator, an eval).
3. **One agent would fill its context with reading** (many documents, many chapters).

| Situation | One agent or team |
|---|---|
| M1–M6 building | One agent. Tightly coupled, sequential by design, small codebase. |
| End-of-milestone review | Optional: one reviewer agent that sees the code, not the builder's reasoning. Only when Jelle asks; `open-pr` already runs a security review. |
| Bulk data entry (SRD stat blocks, scenario adventures, lore files) once the schema is stable | A team may help if there are many items; each item is checked by the loader's validation. |
| M8 conversion of a book | One agent, run as Jelle's session so it can ask him; sub-agents only for self-contained reading (a map, a page of stat blocks), returning a draft and questions. |

A team costs several times the tokens of one agent and each handoff loses detail. When in doubt, one agent.

### 10.2 Which model builds what

Prices per million tokens, input / output (2026-11): Fable 5.2 $8 / $40, Opus 5.5 $4 / $20, Sonnet 5.5 $2 / $10, Haiku 5.5 $0.10 / $0.50. On a subscription, a more expensive model also uses up the usage limit faster (roughly, not exactly by these ratios).

| Model | Use for | Not for |
|---|---|---|
| **Opus 5.5** (default) | All building and design in M1–M9: code, tests, prompts, debugging, planning the next milestone. | — |
| **Fable 5.2** | Hard, high-stakes thinking where a wrong call is expensive: designing the M8 converter and its evals; running the converter agent on a book; a bug or design problem Opus has failed at twice. Switch for that task, then switch back. | Routine milestone work: twice the price of Opus for no visible gain. |
| **Sonnet 5.5** | Mechanical, well-specified work inside a team: transcribing SRD stat blocks into YAML, drafting scenario adventures and lore files against a fixed schema, M8 sub-agents that read one map or one page of stat blocks. | Architecture, the core models, anything that sets a pattern others follow. |
| **Haiku 5.5** | The game's runtime model (interpreter and narrator, see section 2). | Building the game. |

Rule of thumb: the model that *decides* is Opus (Fable when stuck); the model that *fills in* against a validator can be Sonnet.
