"""Turn-0 state built from adventure data. Replay always starts here."""

from collections.abc import Mapping, Sequence

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.state.apply import apply_events
from solo_dm.core.state.models import (
    Character,
    CreatureStatBlock,
    GameState,
    creature_from_stat_block,
)
from solo_dm.core.turn.perception import notice_on_entering


def initial_state(
    adventure: Adventure,
    party: Sequence[Character],
    bestiary: Mapping[str, CreatureStatBlock],
) -> GameState:
    creatures = [
        creature_from_stat_block(bestiary[e.srd_ref], e.id, e.location, e.attitude)
        for e in adventure.entities
    ]
    state = GameState(
        party={member.character_id: member for member in party},
        party_location=adventure.start_location,
        discovered_locations=(adventure.start_location,),
        creatures={c.creature_id: c for c in creatures},
        items_on_floor={i.id: i.location for i in adventure.items if i.location},
        items_carried={i.id: i.carried_by for i in adventure.items if i.carried_by},
        hidden_unfound=tuple(
            thing_id for loc in adventure.locations for thing_id, _ in adventure.hidden_in(loc.id)
        ),
        locked_exits=tuple(lock.exit for lock in adventure.locks if lock.locked),
    )
    # The party looks around the start location too.
    return apply_events(state, notice_on_entering(state, adventure, adventure.start_location))
