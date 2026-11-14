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
├── src/adventure_ingest/     # book -> adventure YAML (M8); imports only solo_dm.core.adventure
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

**Where adventures live (Jelle, 2026-11-14): game and adventure data in separate repos.**
- `dnd-game` (this repo): the engine, web app, ingestion application and tests, plus only the data the tests check the engine with: `core_five_rooms`, the scenarios, their lore, and M8's own small test book.
- `Hopsakee/dnd-adventures` (private, no code): converted books with their gold versions, lore that belongs to a book, and the ingest work folders with the manual model answers. Changed through PRs like this repo.
- The source books (PDFs, maps, zips) stay on Drive: large, unchanging, backed up to the NAS. In the box: `~/transport/dndgame/`.
- The game reads adventures from both places: `settings.yaml` gets a second adventures path, and `compose.yaml` mounts a clone of `dnd-adventures` read-only, so no image contains a copyrighted adventure.
- Supersedes "a gitignored `adventures/private/`" (2026-11-13).

### M8 — Ingestion: book to adventure, a separate application
Decided by Jelle 2026-11-14: converting a book is its own application, not part of the game. Same repo, separate package and command, its own tests and evals.

- **Package `src/adventure_ingest/`** with the command `uv run adventure-ingest`. It may import the engine's adventure schema (`solo_dm.core.adventure`, plus the models that schema uses) and nothing else from `solo_dm`; `solo_dm` never imports it. The architecture test enforces both.
- **Stages with files between them.** Each stage reads the previous stage's file and writes its own, in a work folder per book in `dnd-adventures` (`ingest/<book>/`), so the manual answers are kept and versioned. So a stage can be rerun, inspected, or done by hand by writing its file:
  1. `extract`: PDF (or Fantasy Grounds XML) to text and page images, plus a report of pages that are images with little text (Azzinax page 6).
  2. Model steps, one per part: locations and their descriptions; links between locations; stat blocks; items, locks, checks and hazards; the goal. Each can run **by hand**. The command writes a structured prompt and lists the files to attach (e.g. the map image), Jelle runs it in a Claude chat (Fable), saves the answer in the work folder, and `adventure-ingest check <part>` validates it at once. Running a step through the API instead is a later option, the same prompt with a different runner.
  3. `assemble`: the parts into one `adventure.yaml`, validated by the engine's schema.
  4. `verify`: deterministic playability checks. Every location is reachable; no key is behind its own lock; the win flag can be set; every monster has a stat block; every obstacle can be passed by the hero's abilities.
- **Evals**, in `evals/` and run with `uv run adventure-ingest eval <book>`: the output of a stage against the gold adventure, field by field (locations, links, monsters and where they are, items, locks, checks, hazards, the goal), as precision and recall per field. A model judge only for fuzzy fields, such as whether a description kept its key details. Every in-game error traced back to ingestion becomes a new eval case.
- **Copyright and evals:** the gold adventures of bought or personal-use books live only in the private `dnd-adventures`, so their evals run only where that repo is. For evals that run anywhere (and in `pytest`), the repo gets one small book of our own: an original adventure written as a PDF with a map image, plus its gold.
- SRD 5.2 versus 2014 stat-block layouts are handled in the stat-block step.

**Done when:** Azzinax goes from PDF and map to an adventure that passes `verify`, with the manual steps done by Jelle, and `eval` shows how close it comes to the gold; the repo's own book passes its evals in `pytest`.

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
| M8 ingestion (per chapter or per book) and running evals against several gold adventures | Team. Truly independent pieces, each checked by evals. Decide the shape when M8 starts. |

A team costs several times the tokens of one agent and each handoff loses detail. When in doubt, one agent.

### 10.2 Which model builds what

Prices per million tokens, input / output (2026-11): Fable 5.2 $8 / $40, Opus 5.5 $4 / $20, Sonnet 5.5 $2 / $10, Haiku 5.5 $0.10 / $0.50. On a subscription, a more expensive model also uses up the usage limit faster (roughly, not exactly by these ratios).

| Model | Use for | Not for |
|---|---|---|
| **Opus 5.5** (default) | All building and design in M1–M9: code, tests, prompts, debugging, planning the next milestone. | — |
| **Fable 5.2** | Hard, high-stakes thinking where a wrong call is expensive: designing the M8 ingestion pipeline and its evals; a bug or design problem Opus has failed at twice. Switch for that task, then switch back. | Routine milestone work: twice the price of Opus for no visible gain. |
| **Sonnet 5.5** | Mechanical, well-specified work inside a team: transcribing SRD stat blocks into YAML, drafting scenario adventures and lore files against a fixed schema, M8 per-chapter workers. | Architecture, the core models, anything that sets a pattern others follow. |
| **Haiku 5.5** | The game's runtime model (interpreter and narrator, see section 2). | Building the game. |

Rule of thumb: the model that *decides* is Opus (Fable when stuck); the model that *fills in* against a validator can be Sonnet.
