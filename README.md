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
