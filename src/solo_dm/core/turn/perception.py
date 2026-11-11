"""Noticing hidden things (M2.5): passive Perception on entering a location.
An active search is the "search" action in resolve.py."""

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.rules.rules_checks import passive_perception
from solo_dm.core.state.events import HiddenFound
from solo_dm.core.state.models import GameState


def notice_on_entering(
    state: GameState, adventure: Adventure, location_id: str
) -> list[HiddenFound]:
    """The party member with the best passive Perception notices every unfound
    hidden thing here whose DC it meets. No dice: passive scores are fixed."""
    watchers = [m for m in state.party.values() if not m.defeated]
    if not watchers:
        return []
    best = max(watchers, key=passive_perception)
    score = passive_perception(best)
    return [
        HiddenFound(actor_id=best.character_id, target_id=thing_id, method="passive")
        for thing_id, dc in adventure.hidden_in(location_id)
        if thing_id in state.hidden_unfound and score >= dc
    ]
