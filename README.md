# solo-dm

A solo Dungeons & Dragons 5e engine. Deterministic Python owns all game state and
rules; a language model only interprets the player's words and narrates outcomes
Python already decided. See [BUILD_PLAN.md](BUILD_PLAN.md) for the plan and
milestones.

## Status

M2: the five-room adventure `core_five_rooms` plays in the terminal with a fake
model (a keyword interpreter and plain narration; the real model arrives in M3):

```bash
uv run solo-dm play            # random dice
uv run solo-dm play --seed 0   # reproducible game
uv run solo-dm play --adventure scenarios/locked_door
```

Try `go north`, `attack goblin`, `search`, `search goblin`, `take key`,
`unlock north`, and the built-in commands `inv`, `hp`, `look`, `map`,
`flag <note>`, `help`, `quit`.

M2.5 adds hidden things. On entering a room the party's best passive Perception
(10 + Wisdom modifier + proficiency if proficient) finds every hidden item or
exit whose DC it meets. `search` rolls Wisdom (Perception) for the rest and can
be tried again. A dead creature's belongings appear when you search its body.

M3: the real model. Claude Haiku 5.5 interprets free text into an intent and
narrates the outcome Python decided. Anything without a rule of its own
(persuading, climbing, forcing) becomes an ability check: the model picks the
ability and how hard the task is, Python sets the DC and rolls, and only
consequences written in the adventure change the game.

```bash
uv run solo-dm play                       # with Haiku (in the box: via the broker)
uv run solo-dm play --fake                # the keyword model: no network, no cost
uv run solo-dm play --adventure scenarios/ability_check
uv run solo-dm cost                       # model spend per day and per campaign
```

Shortcuts: `a` is attack (`a goblin`), `n`/`s`/`e`/`w` go that way, `i` shows
what you wear, wield and carry. A location in an adventure may have `senses:`
(a smell or sound, e.g. `woodsmoke`), which the rooms next door can notice;
keep it to things that do not change in play.

In play, `cost` shows this session's spend, and quitting prints it. Every call
is logged to `logs/llm_calls.jsonl` (tokens and estimated cost, no text);
`settings.yaml` sets a daily cap (`cost.daily_cap_usd`).

M4: campaigns. Every `play` starts a numbered campaign, stored after every turn
in `campaigns/campaigns.db` (SQLite, gitignored) with a frozen copy of the
adventure, so stopping is just `quit`:

```bash
uv run solo-dm campaigns                  # list them, with turns and outcome
uv run solo-dm play --campaign 1          # resume campaign 1
uv run solo-dm rewind 1 2                 # back to the state after turn 2 (0: the start)
uv run solo-dm turns 1                    # every turn, superseded ones too
uv run solo-dm turns 1 --fallback         # ability-check fallbacks: mechanics to build next
uv run solo-dm turns 1 --rejected         # intents that failed validation twice
```

A rewind deletes nothing: later turns are marked superseded and stay in
`turns`. The event log is the truth; a test checks that replaying it from the
start gives the stored snapshot.

M5: lore. Markdown files in `lore/`, one per topic, with front matter:

```markdown
---
title: Goblins of the Hill Country
tags: [goblin]
---
Background the character may know...
```

At start the files are indexed in SQLite FTS5 (in memory, so an edited file is
picked up at the next start). The scene gets the lore whose tags match the
location or a creature or item that is visible there, and the interpreter can
ask for more with `lore_query` ("what do I remember about the shrine?"). Lore
only colours interpretation and narration; it never changes what happens. Items
in an adventure may have a `description`, which the narrator follows instead of
inventing properties.

M6: the web app, for playing from a phone. The same campaigns as the terminal:
a game started in one resumes in the other.

```bash
uv run solo-dm web                        # http://127.0.0.1:5001
uv run solo-dm web --port 8080
```

Home offers to continue the latest campaign; Campaigns lists them all and starts
a new game. In a campaign: Play (the story, a box with the room, buttons for
what can be done here and an input line that takes the same shortcuts and
commands as the terminal), Character, Inventory and Map (the discovered rooms,
yours highlighted). Cost shows the model spend.

It listens on 127.0.0.1 only. Tailscale is the only gate: the app has no login.

To play from the phone, run it in Docker (`Dockerfile`, `compose.yaml`) next to
a Tailscale container that joins the tailnet as the machine `solo-dm` and
forwards `https://solo-dm.<tailnet>.ts.net` to the game. No port is published
on the host. On the Mac mini (OrbStack), in a clone of this repo:

```bash
echo 'TS_AUTHKEY=tskey-auth-...' > .env.tailscale   # from the Tailscale admin console
echo 'ANTHROPIC_API_KEY=...' > .env.solo_dm         # mounted read-only, not in the image
docker compose up -d --build
docker compose logs -f                              # the tailnet address appears here
docker compose exec solo-dm solo-dm play            # terminal play, same campaigns
```

Campaigns and the cost log live in the volumes `campaigns` and `logs`, not in
the clone. The image installs the exact versions `uv.lock` pins, from PyPI (the
lock itself names the development box's wheel store). After the first login the
`tailscale-state` volume keeps the machine on the tailnet, so `.env.tailscale`
can go.

The app is built with `FastHTML()` and serves only `static/`. htmx 2.0.7 and
fasthtml.js 1.0.12 are vendored in `static/vendor/`, so pages load nothing from
a CDN; upgrading htmx means replacing that file. Not `fast_app()`: it adds a
route that serves any `.yaml`, `.txt` and similar file under the working
directory, `..` included.

M7: what Revenge of Azzinax needs. Adventures can now have:

- `hazards` in a location: a trap with a saving throw (`save: {ability, dc}`),
  damage on a failure, and optionally `hidden: {dc}`, so that noticing it
  (passive Perception or a search) avoids it. A trap springs once.
- `force_dc` on a lock: a stuck door, forced open with Strength (Athletics);
  `open`, `force north` or `kick the door`.
- `uses` in a location: using a carried item there sets a flag
  (`toss the coin into the fountain`), and locks with `opens_on_flag` open on it.
- `effect: {heal: 2d4+2}` on an item: a potion, used up when drunk.
- `guardian: {name, rescues}`: someone who brings the hero back to full hit
  points instead of a defeat, that many times.
- `dc` on a check: the DC the book states, instead of one Python derives.
- `creatures/<id>.yaml` next to an adventure: its own stat blocks, for monsters
  outside the SRD.

The Fighter now makes saving throws (proficient in STR and CON). Each mechanic
has a scenario in `adventures/scenarios/`. Books live in the private repo
`dnd-adventures`, cloned next to this one: `settings.yaml` reads
`extra_adventures: [../dnd-adventures]`, and in Docker `compose.yaml` mounts
that clone, so on the Mac clone it next to `dnd-game` before
`docker compose up`.

## Commands

```bash
uv run pytest            # unit tests and the core import rule
uv run pytest -m live    # real-model tests (deselected by default; costs a little)
uv run ruff check
uv run solo-dm --help
```

Settings live in `settings.yaml`. In the development box, model calls go to the
credential broker named by `$ANTHROPIC_API_BASE`, which adds the key. Anywhere
else, put the key in `.env.solo_dm` (gitignored) as `ANTHROPIC_API_KEY=...`.
Prompts live in `src/solo_dm/infrastructure/llm/prompts/`.

## Layout

- `src/solo_dm/core/`: rules, state, events, ports. Pure Python and Pydantic only;
  `tests/test_architecture.py` fails on any other import.
- `src/solo_dm/infrastructure/`: adapters (dice, SRD data, settings).
- `srd/`: SRD 5.2 data the engine uses, as YAML.
- `adventures/`: `core_five_rooms` (smoke test) and one scenario per mechanic.

## Python version

The project pins Python 3.12 because the development box has 3.12 and its wheel
store holds `cp312` wheels. The code uses nothing newer than 3.12 and should run
on 3.14 unchanged; switching is `.python-version` plus `uv lock`.

## Where packages come from (box versus your own machine)

`uv.lock` records which version of each package to install, and also where uv
gets it from: the `source = { registry = ... }` line of each package.

- On your own machine, uv downloads packages from PyPI (pypi.org), its default.
- In the development box, uv cannot reach PyPI. It installs only from the box's
  approved wheel store, `/opt/wheels`. So a lock written in the box records
  `registry = "/opt/wheels"`, a folder that exists nowhere else.

If `uv sync` on your own machine fails with
`failed to query metadata of file /opt/wheels/...`, the lock was last written in
the box. Delete the lock, lock again against PyPI, and sync. A plain `uv lock`
is not enough: uv sees the old lock as still valid and keeps its sources.

```bash
rm uv.lock
uv lock
grep -c /opt/wheels uv.lock   # expect 0
uv sync
```

That lock can be committed. For the same reason, a lock written in the box
should not go into a pull request.

## Licence and attribution

This work includes material from the System Reference Document 5.2 ("SRD 5.2")
by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The
SRD 5.2 is licensed under the Creative Commons Attribution 4.0 International
License, available at https://creativecommons.org/licenses/by/4.0/legalcode.
