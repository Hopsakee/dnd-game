"""Hazards and traps (M7): what springs when the party enters a location."""

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.ports import DicePort
from solo_dm.core.rules.dice_expression import parse_dice
from solo_dm.core.rules.rules_checks import saving_throw
from solo_dm.core.rules.rules_defeat import dropped_to_zero
from solo_dm.core.state.apply import apply_events
from solo_dm.core.state.events import AdventureLost, DamageDealt, Event, HazardSprung
from solo_dm.core.state.models import GameState


def spring_hazards(state: GameState, adventure: Adventure, location_id: str,
                   dice: DicePort) -> list[Event]:
    """Every hazard here that is neither noticed nor sprung before goes off."""
    events: list[Event] = []
    for hazard in adventure.location(location_id).hazards:
        noticed = hazard.hidden is not None and hazard.id not in state.hidden_unfound
        if noticed or hazard.id in state.sprung_hazards:
            continue
        events.append(HazardSprung(hazard_id=hazard.id, name=hazard.name))
        for member_id in state.party:
            member = apply_events(state, events).party[member_id]  # earlier traps count
            if member.defeated:
                continue
            save = saving_throw(member, hazard.save.ability, hazard.save.dc, dice)
            events.append(save)
            if save.success:
                continue
            damage = parse_dice(hazard.damage_dice)
            rolls = dice.roll(f"{damage.count}d{damage.sides}").rolls
            amount = max(0, sum(rolls) + damage.modifier)
            events.append(DamageDealt(target_id=member_id, rolls=rolls,
                                      modifier=damage.modifier, amount=amount,
                                      damage_type=hazard.damage_type))
            if member.hp - amount <= 0:
                events.append(dropped_to_zero(apply_events(state, events), member_id, None))
    after = apply_events(state, events)
    if events and all(m.defeated for m in after.party.values()):
        events.append(AdventureLost(reason="every party member fell to a hazard"))
    return events
