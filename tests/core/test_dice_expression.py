import pytest

from solo_dm.core.rules.dice_expression import DiceExpression, parse_dice


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1d20", DiceExpression(count=1, sides=20, modifier=0)),
        ("2d6+3", DiceExpression(count=2, sides=6, modifier=3)),
        ("1d8-1", DiceExpression(count=1, sides=8, modifier=-1)),
        ("d4", DiceExpression(count=1, sides=4, modifier=0)),
    ],
)
def test_parses_standard_dice_notation(text, expected):
    assert parse_dice(text) == expected


@pytest.mark.parametrize("text", ["", "20", "1d", "2x6", "1d0", "0d6"])
def test_rejects_malformed_expressions(text):
    with pytest.raises(ValueError):
        parse_dice(text)
