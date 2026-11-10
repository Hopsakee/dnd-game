"""Reproducible dice for tests and scripted playthroughs."""

import random

from solo_dm.infrastructure.dice.random_dice import RandomDice


class SeededDice(RandomDice):
    def __init__(self, seed: int) -> None:
        super().__init__(random.Random(seed))
