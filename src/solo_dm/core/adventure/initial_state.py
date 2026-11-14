"""Turn-0 state built from adventure data. Replay always starts here."""

from collections.abc import Mapping, Sequence

from solo_dm.core.adventure.schema import PARTY, Adventure
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
    own = tuple(i.id for i in adventure.items if i.carried_by == PARTY)
    first, *others = party
    party = [first.model_copy(update={"inventory": (*first.inventory, *own)}), *others]
    state = GameState(
        party={member.character_id: member for member in party},
        party_location=adventure.start_location,
        discovered_locations=(adventure.start_location,),
        creatures={c.creature_id: c for c in creatures},
        items_on_floor={i.id: i.location for i in adventure.items if i.location},
        items_carried={i.id: i.carried_by for i in adventure.items
                       if i.carried_by not in (None, PARTY)},
        hidden_unfound=tuple(
            thing_id for loc in adventure.locations for thing_id, _ in adventure.hidden_in(loc.id)
        ),
        locked_exits=tuple(lock.exit for lock in adventure.locks if lock.locked),
        guardian=adventure.guardian.name if adventure.guardian else None,
        rescues_left=adventure.guardian.rescues if adventure.guardian else 0,
    )
    # The party looks around the start location too.
    return apply_events(state, notice_on_entering(state, adventure, adventure.start_location))
