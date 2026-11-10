from solo_dm.infrastructure.dice.random_dice import RandomDice
from solo_dm.infrastructure.dice.seeded_dice import SeededDice


def test_seeded_dice_repeat_the_same_rolls_for_the_same_seed():
    a, b = SeededDice(seed=7), SeededDice(seed=7)
    assert [a.roll("1d20") for _ in range(20)] == [b.roll("1d20") for _ in range(20)]


def test_roll_result_adds_the_modifier_to_the_dice():
    result = SeededDice(seed=1).roll("2d6+3")
    assert len(result.rolls) == 2
    assert result.modifier == 3
    assert result.total == sum(result.rolls) + 3


def test_random_dice_stay_within_the_faces():
    dice = RandomDice()
    faces = {face for _ in range(500) for face in dice.roll("1d4").rolls}
    assert faces == {1, 2, 3, 4}
