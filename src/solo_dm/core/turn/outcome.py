"""What the narrator receives: the decided outcome of one turn."""

from pydantic import BaseModel

from solo_dm.core.state.events import Event
from solo_dm.core.turn.intent import Intent


class TurnOutcome(BaseModel):
    actor_id: str
    intent: Intent
    events: list[Event]
    blocked: str | None = None
    # The player's own words, so a question in them gets answered; they never
    # change what happened (play-test flag 5, 2026-11-13).
    player_input: str = ""
