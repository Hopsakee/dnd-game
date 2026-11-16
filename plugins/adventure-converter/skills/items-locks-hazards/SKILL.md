---
name: items-locks-hazards
description: The items, locks and hazards step of converting an adventure for solo-dm. Writes items.yaml - every item and its use (coins, weapons, healing, keys, the goal item, a choice of rewards), locks on both sides of a door (key, pick, force, a mechanism's flag), traps and hazards with their save, damage or condition, uses of an item or coins in a place, arrivals, and the win flag. Use in the adventure-converter's step 4.
---

# Items, locks and hazards: items.yaml

Schema: `adventure-ingest schema items`. Example:
`../dnd-game/evals/millers_cellar/stages/items.yaml`.

## win_condition

The flag that wins the adventure, and something must set it: taking an item
(`on_take`), a challenge, a use, or arriving somewhere (`arrivals`). The win
is where the book's hook ends: coming back to the quest-giver with what they
asked for is an arrival that `requires` the flag of having it. When the book
asks for more than one thing (find the relic *and* defeat its keeper), one
flag still wins: the last step, with `requires` on the steps before.

## items

- `location` (a place id) or `carried_by` (a creature id, dropped when its body
  is searched, or `party` for what the hero starts with). Never both.
- `hidden: {dc}` for anything found only by searching or noticing (Perception,
  Investigation). The DC is the book's.
- `coins: {gp, sp, cp, pp}` for money; taking it fills the purse. A gem or art
  object is a separate item with its worth in the description.
- `weapon` for a weapon the hero can wield: `damage_dice`, `damage_type`, the
  ability, and `damage_penalty` (dice subtracted, a curse). The book gives no
  stats: use the SRD weapon's.
- `effect: {heal}` for a potion: used up when drunk.
- `on_take: {set_flag}` for an item whose taking matters (the goal item).
- `description`: what it looks like, in your words. The narrator invents no
  other properties, so a magic item's effect the engine cannot hold goes in
  questions.md under "Engine gaps", not here.
- `requires: {flags, not_flags, defeated}`: the item is only there while it
  holds. **A reward the hero chooses between** (coins now or an item
  instead): both items, each with `on_take` setting its own flag and
  `requires: {not_flags: [the other's flag]}`, so taking one makes the other
  go. Example: Wenna's potion and silver in the test book's
  `stages/items.yaml`. A reward paid after the win changes nothing in play:
  leave it to the ending.
- **A container is one thing** (a box holding coins and a gem). The
  engine has no containers: write the contents as items in its place, and
  say in each description that it lies in the box.
- **Out of sight, not hidden.** `hidden` is for what a Perception or
  Investigation check finds. A thing in plain view from a spot the hero must
  first reach (a loft, a ledge) is not hidden: it lies in the place inside
  the room (skill `map`), in plain view there. Example: Bram's savings box.

## locks

A door is two exits, one per side (`3a` and `c3b`), and the engine opens both
when one opens. **Lock both sides, with the same lock.** When the book calls a
door locked or sealed on one side only, it is locked on both: do not ask
(Jelle, 2026-11-16). Only a book that explains why a door opens from one side
alone (a bar on the inside) is a question.

- `key`: the item that opens it. Never put a key behind the lock it opens.
- `pick_dc`: a lock that can be picked.
- `force_dc`: a stuck door, forced with Strength (Athletics). When the book
  gives no DC: 10 for a simple wooden door, 15 for a good wooden or iron door;
  say so in questions.md.
- `opens_on_flag`: a door opened by a mechanism (a lever, a turned millstone). The flag is set by a challenge or a use.

## uses

`{at, item | pay, set_flag, requires}`: using an item in a place, or paying
coins there (`pay: 1` for "a coin of any kind"), sets a flag.

## arrivals

`{at, set_flag, requires}`: arriving in a place sets a flag once `requires`
holds. For the win on coming back (the test book: the yard, with the ledger).

## hazards

`{at, id, name, save: {ability, dc}, damage_dice, damage_type, condition,
hidden}`: a trap or hazard springs on entering its place; each hero saves or
takes the damage, gains the condition, or both.
`condition: disadvantage_on_next_roll` for "disadvantage on the next attack
roll, ability check or saving throw" (the test book's flour dust).
`hidden: {dc}` when noticing it avoids it (the book's Perception DC). A trap
with an attack roll instead of a save: nearest save, listed under "Engine
gaps". Another condition (poisoned, prone): leave it out and list it; never
invent damage for it.

## Ask Jelle when

- A door opens from one side only and the book says why, or the book is
  silent on how it opens.
- A DC is missing.

## Before you go on

```bash
uv run --project ../dnd-game adventure-ingest check items ingest/<book_id>
```

Then count: every door the book calls locked, stuck, barred or sealed has a lock
on both sides, and every treasure the book lists is an item.
