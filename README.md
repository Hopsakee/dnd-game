# solo-dm

A solo Dungeons & Dragons 5e engine. Deterministic Python owns all game state and
rules; a language model only interprets the player's words and narrates outcomes
Python already decided. See [BUILD_PLAN.md](BUILD_PLAN.md) for the plan and
milestones.

## Status

M1 (core skeleton): game state with a party, events and `apply_event`, dice,
ability checks, attacks, damage, creature death and combat rounds. Nothing to
play yet; `solo-dm play` arrives in M2.

## Commands

```bash
uv run pytest            # unit tests and the core import rule
uv run pytest -m live    # real-model tests (from M3; deselected by default)
uv run ruff check
uv run solo-dm --help
```

Settings live in `settings.yaml`. An API key, only when running outside the
development box, goes in `.env.solo_dm` (gitignored) as `ANTHROPIC_API_KEY=...`.

## Layout

- `src/solo_dm/core/`: rules, state, events, ports. Pure Python and Pydantic only;
  `tests/test_architecture.py` fails on any other import.
- `src/solo_dm/infrastructure/`: adapters (dice, SRD data, settings).
- `srd/`: SRD 5.2 data the engine uses, as YAML.

## Python version

The project pins Python 3.12 because the development box has 3.12 and its wheel
store holds `cp312` wheels. The code uses nothing newer than 3.12 and should run
on 3.14 unchanged; switching is `.python-version` plus `uv lock`.

## Licence and attribution

This work includes material from the System Reference Document 5.2 ("SRD 5.2")
by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The
SRD 5.2 is licensed under the Creative Commons Attribution 4.0 International
License, available at https://creativecommons.org/licenses/by/4.0/legalcode.
