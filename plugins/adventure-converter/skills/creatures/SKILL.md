---
name: creatures
description: The creatures step of converting an adventure for solo-dm. Writes creatures.yaml (who is where, their attitude, group and activity, and the guardian) and a stat block in creatures/ for every creature the SRD folder lacks, from SRD 5.2 or 2014-style stat blocks. Use in the adventure-converter's step 3.
---

# Creatures: creatures.yaml and creatures/*.yaml

Schemas: `adventure-ingest schema creatures` and `adventure-ingest schema
stat-block`. Example: `../dnd-game/evals/millers_cellar/stages/creatures.yaml`
and `stages/creatures/old_grist.yaml` (read from a stat block printed as a
picture, `book/old_grist.png`).

## creatures.yaml

One entry per creature, not per kind: two goblin warriors are `goblin_1` and
`goblin_2`.

- `srd_ref`: the stat block's id. The engine's SRD stat blocks are the files in
  `../dnd-game/srd/creatures/`; for anything else write `creatures/<id>.yaml`.
  Check that folder, do not assume a monster is there because it is in the SRD.
- `location`: a place id from `map.yaml`. A creature the book places at a
  corridor letter goes in that corridor.
- `attitude`: `hostile` when it attacks on sight; `indifferent` when it talks,
  waits or ignores the hero first; `friendly` when it helps.
- `activity`: what it is doing when the hero arrives ("sits at the table
  counting coins"), in your words. Shown until it turns hostile.
- `group`: creatures that fight together get the same group: attack one and all
  turn hostile. Ask Jelle when the book does not say whether a lurking creature
  joins a fight.
- `tags`: only when the book groups creatures with places (a smugglers' hideout).
- A check that talks a creature round (persuade, intimidate, bribe) is a
  challenge: the `challenges` step writes it at the creature.
- `guardian`: someone who rescues the hero at 0 hit points, with how many times.
  Only when the book has such a helper.

The engine cannot hold yet: hidden creatures, ambush or surprise, creatures that
appear on a trigger, allies that fight. Place such a creature where it is when
the hero meets it, and list the simplification in questions.md under
"Simplified".

## A stat block: creatures/<stat_block_id>.yaml

- `armor_class`, `hit_points` (the average, not the dice), `abilities` (the
  six scores, not the modifiers).
- `initiative_bonus`: SRD 5.2 prints "Initiative +2"; a 2014-style block does
  not, so use the DEX modifier.
- `attacks`: melee only. SRD 5.2 writes "Melee Attack Roll: +4 ... Hit: 5 (1d6 +
  2) Slashing damage"; 2014 writes "Melee Weapon Attack: +4 to hit ... Hit: 5
  (1d6 + 2) slashing damage". Either way: `attack_bonus: 4`, `damage_dice: 1d6`,
  `damage_modifier: 2`, `damage_type: slashing`. A damage without a modifier has
  `damage_modifier: 0`.
- `not_implemented`: every trait, ranged attack, spell or reaction the engine
  cannot use, by name, so the narrator does not invent it.
- A stat block printed as a picture: `extract.md` lists its page. Read the
  image; when it is hard to read, say so in questions.md and ask Jelle to check
  the numbers.

## Before you go on

```bash
uv run --project ../dnd-game adventure-ingest check creatures ingest/<book_id>
```

Then count: every creature the book names in a room or corridor has an entry,
and every `srd_ref` has a stat block.
