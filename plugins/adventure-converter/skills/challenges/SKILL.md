---
name: challenges
description: The challenges step of converting an adventure for solo-dm. Writes challenges.yaml - every ability check the book sets that changes something, as a challenge with an id, the goal the hero pursues, ability, skill, DC and the flag success sets, placed at a location or a creature (the check that talks a creature round). Use in the adventure-converter's step 5.
---

# Challenges: challenges.yaml

Schema: `adventure-ingest schema challenges`. Example:
`../dnd-game/evals/millers_cellar/stages/challenges.yaml`.

A challenge is a goal the hero can attempt, and the check the book sets for
it. The models in the game see the goal, and any attempt at it rolls this
check: so the goal decides when the check is rolled. In the Azzinax play test a
missing goal meant the game asked for the wrong roll.

## One challenge

- `at`: the place where it can be attempted, or the creature it is about.
- `id`: short and descriptive, `turn_millstone`, `persuade_grist`.
- `goal`: what the attempt achieves, as the hero's aim, in a few words: "turn
  the jammed millstone a full circle". Not the method: pushing it and levering
  it with a beam are both attempts at that goal.
- `ability`, `skill` (lower case, `athletics`), `dc`: as the book says. A check
  the book sets without a DC: ask Jelle, or leave `dc` out so the engine sets
  it from the task's difficulty.
- `on_success: {set_flag}`: the flag a lock (`opens_on_flag`) or the win reads.

## Not a challenge

- A check to notice or find something: that is `hidden: {dc}` on the item,
  exit or hazard.
- A saving throw against a trap: a hazard (`items-locks-hazards`).
- Forcing a stuck door or picking a lock: the lock's `force_dc` or `pick_dc`.
- A check whose success changes nothing the engine tracks (recalling lore): the
  narrator handles it; leave it out.

## Talking a creature round

The check that makes a creature give in, hand something over or let the hero
pass is a challenge `at` that creature. Its flag is what the talk wins (the
goal item, an open door). Ask Jelle when the book leaves open what a successful
talk gets.

The engine cannot hold yet: a check with a precondition (only after the boss is
dead), a cost on failure (fall damage), a DC that changes after a failure.
The book is clear about these, so they are not questions: write the plain
check with the book's first DC and list the rest under "Engine gaps".

## Before you go on

```bash
uv run --project ../dnd-game adventure-ingest check challenges ingest/<book_id>
```

Then every flag in `items.yaml` (`opens_on_flag`, `win_condition`) must be set
by a challenge, a use or `on_take`: `assemble` reports a flag nobody sets.
