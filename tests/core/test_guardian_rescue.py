"""M7: a guardian (Revenge of Azzinax: Spiritus Magehunter) brings the hero back
to full hit points the first time they drop to 0, instead of a defeat."""

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.rules.rules_attacks import resolve_attack
from solo_dm.core.state.apply import apply_events

from ..fakes import FixedDice
from .adventure_fixture import BESTIARY, tiny_adventure
from .builders import fighter

SPIRITUS = {"name": "Spiritus Magehunter", "rescues": 1}


def goblin_hits(state, faces):
    goblin = state.creatures["goblin"]
    events = resolve_attack(state, "goblin", "hero", goblin.attacks[0], FixedDice(faces))
    return [e.type for e in events], apply_events(state, events)


def test_the_guardian_saves_the_hero_once():
    adventure = tiny_adventure(guardian=SPIRITUS)
    state = initial_state(adventure, [fighter(hp=3)], BESTIARY)
    types, after = goblin_hits(state, [15, 4])  # hits AC 17 (15 + 4); 4 + 2 = 6 damage
    assert types == ["attack_rolled", "damage_dealt", "guardian_rescued"]
    assert after.party["hero"].hp == 12 and not after.party["hero"].defeated

    worn = after.model_copy(update={"party": {"hero": after.party["hero"].model_copy(
        update={"hp": 3})}})
    types, after = goblin_hits(worn, [15, 4])
    assert types[-1] == "character_defeated"  # the rescue is spent


def test_without_a_guardian_zero_hit_points_is_a_defeat():
    state = initial_state(tiny_adventure(), [fighter(hp=3)], BESTIARY)
    assert goblin_hits(state, [15, 4])[0][-1] == "character_defeated"


def test_the_guardian_also_saves_the_hero_from_a_trap():
    from .test_hazards import enter_den, with_hazard

    adventure = with_hazard().model_copy(update={"guardian": tiny_adventure(
        guardian=SPIRITUS).guardian})
    types, after = enter_den(adventure, [1, 4], hero=fighter(hp=3))
    assert types[-1] == "guardian_rescued" and after.outcome == "playing"
