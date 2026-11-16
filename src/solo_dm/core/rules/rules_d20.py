"""The d20 (M8.5): every attack roll, ability check and saving throw a
character makes. With advantage roll two and keep the higher, with
disadvantage the lower; both at once cancel (SRD 5.2)."""

from typing import Literal

from solo_dm.core.ports import DicePort
from solo_dm.core.state.models import Character

RollMode = Literal["advantage", "disadvantage"] | None

# A condition: disadvantage on the next attack roll, ability check or saving
# throw, used up by that roll (Azzinax: the mushroom gas).
DISADVANTAGE_ON_NEXT_ROLL = "disadvantage_on_next_roll"
CONDITIONS = (DISADVANTAGE_ON_NEXT_ROLL,)


def roll_d20(dice: DicePort, *, advantage: bool = False, disadvantage: bool = False
             ) -> tuple[int, list[int], RollMode]:
    """(the die kept, every die rolled, the mode)."""
    if advantage == disadvantage:
        rolls = dice.roll("1d20").rolls
        return rolls[0], rolls, None
    rolls = dice.roll("2d20").rolls
    if advantage:
        return max(rolls), rolls, "advantage"
    return min(rolls), rolls, "disadvantage"


def character_d20(character: Character, dice: DicePort
                  ) -> tuple[int, list[int], RollMode, str | None]:
    """A character's d20: (kept, rolled, mode, the condition this roll uses up)."""
    ends = DISADVANTAGE_ON_NEXT_ROLL if DISADVANTAGE_ON_NEXT_ROLL in character.conditions else None
    kept, rolls, mode = roll_d20(dice, disadvantage=ends is not None)
    return kept, rolls, mode, ends
