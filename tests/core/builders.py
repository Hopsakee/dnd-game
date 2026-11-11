"""Small, explicit test characters and creatures (literal numbers, not the premade)."""

from solo_dm.core.state.models import (
    AbilityScores,
    AttackProfile,
    Character,
    CreatureState,
    GameState,
    Weapon,
)

GREATSWORD = Weapon(
    weapon_id="greatsword", name="Greatsword", ability="STR", damage_dice="2d6",
    damage_type="slashing",
)


def fighter(character_id: str = "hero", hp: int = 12) -> Character:
    return Character(
        character_id=character_id,
        name=character_id.title(),
        player_id="jelle",
        level=1,
        abilities=AbilityScores(STR=16, DEX=14, CON=15, INT=8, WIS=12, CHA=10),
        max_hp=12,
        hp=hp,
        armor_class=17,
        proficiency_bonus=2,
        skill_proficiencies=("athletics", "perception"),
        weapons=(GREATSWORD,),
    )


def goblin(creature_id: str = "goblin", hp: int = 10, location: str = "cave"):
    return CreatureState(
        creature_id=creature_id,
        name="Goblin Warrior",
        srd_ref="goblin_warrior",
        location=location,
        attitude="hostile",
        armor_class=15,
        max_hp=10,
        hp=hp,
        initiative_bonus=2,
        attacks=(
            AttackProfile(
                name="Scimitar", attack_bonus=4, damage_dice="1d6",
                damage_modifier=2, damage_type="slashing",
            ),
        ),
    )


def state_with(*members, creatures=(), location: str = "cave"):
    return GameState(
        party={m.character_id: m for m in members},
        party_location=location,
        creatures={c.creature_id: c for c in creatures},
    )
