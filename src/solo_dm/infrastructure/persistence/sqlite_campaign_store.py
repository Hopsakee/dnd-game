"""Campaigns in one SQLite file (plan 4.2). Each turn is written in a single
transaction: the turn row, its events and the snapshot after it. A rewind marks
later turns superseded and never deletes them."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.ports import CampaignStorePort, CampaignSummary
from solo_dm.core.state.events import event_from_stored
from solo_dm.core.state.models import GameState
from solo_dm.core.turn.intent import Intent
from solo_dm.core.turn.session import StoredCampaign, TurnRecord

SCHEMA = """
create table if not exists campaigns (
    campaign_id integer primary key,
    adventure_id text not null,
    title text not null,
    created_at text not null,
    adventure_copy text not null,     -- frozen adventure JSON
    initial_state text not null       -- turn-0 state JSON, incl. the party; replay starts here
);
create table if not exists players (
    campaign_id integer not null references campaigns,
    player_id text not null,
    display_name text not null,
    primary key (campaign_id, player_id)
);
create table if not exists turns (
    turn_id integer primary key,
    campaign_id integer not null references campaigns,
    turn_number integer not null,
    created_at text not null,
    actor_id text not null,
    player_id text not null,
    player_input text not null,
    intent text,                      -- intent JSON; null when none was valid
    validation_error text,
    fallback integer not null,
    compound integer not null,
    narration text not null,
    flag_note text,
    superseded_at text                -- set by a rewind; null while the turn is in play
);
create table if not exists events (
    turn_id integer not null references turns,
    sequence integer not null,
    event_type text not null,
    actor_id text,
    payload text not null,
    primary key (turn_id, sequence)
);
create table if not exists snapshots (
    turn_id integer primary key references turns,
    state text not null
);
"""


class UnknownCampaign(ValueError):
    pass


class LoggedTurn(TurnRecord):
    """A turn as logged, including turns a rewind superseded."""

    superseded: bool


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SQLiteCampaignStore(CampaignStorePort):
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("pragma foreign_keys = on")
        self._db.executescript(SCHEMA)

    def create(self, adventure: Adventure, initial_state: GameState) -> int:
        with self._db:
            cursor = self._db.execute(
                "insert into campaigns (adventure_id, title, created_at, adventure_copy,"
                " initial_state) values (?, ?, ?, ?, ?)",
                (adventure.id, adventure.title, _now(), adventure.model_dump_json(),
                 initial_state.model_dump_json()),
            )
            campaign_id = cursor.lastrowid
            players = {m.player_id for m in initial_state.party.values()}
            self._db.executemany(
                "insert into players values (?, ?, ?)",
                [(campaign_id, p, p) for p in sorted(players)],
            )
        return campaign_id

    def record_turn(self, campaign_id: int, turn: TurnRecord, state: GameState) -> None:
        with self._db:
            cursor = self._db.execute(
                "insert into turns (campaign_id, turn_number, created_at, actor_id, player_id,"
                " player_input, intent, validation_error, fallback, compound, narration,"
                " flag_note) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (campaign_id, turn.turn_number, _now(), turn.actor_id, turn.player_id,
                 turn.player_input, turn.intent.model_dump_json() if turn.intent else None,
                 turn.validation_error, turn.fallback, turn.compound, turn.narration,
                 turn.flag_note),
            )
            turn_id = cursor.lastrowid
            self._db.executemany(
                "insert into events values (?, ?, ?, ?, ?)",
                [(turn_id, seq, e.type, e.actor_id, e.model_dump_json())
                 for seq, e in enumerate(turn.events)],
            )
            self._db.execute("insert into snapshots values (?, ?)",
                             (turn_id, state.model_dump_json()))

    def flag_turn(self, campaign_id: int, turn_number: int, note: str) -> None:
        with self._db:
            self._db.execute(
                "update turns set flag_note = ? where campaign_id = ? and turn_number = ?"
                " and superseded_at is null",
                (note, campaign_id, turn_number),
            )

    def load(self, campaign_id: int) -> StoredCampaign:
        campaign = self._campaign_row(campaign_id)
        rows = self._db.execute(
            "select * from turns where campaign_id = ? and superseded_at is null"
            " order by turn_number",
            (campaign_id,),
        ).fetchall()
        initial = GameState.model_validate_json(campaign["initial_state"])
        state = initial
        if rows:
            snapshot = self._db.execute(
                "select state from snapshots where turn_id = ?", (rows[-1]["turn_id"],)
            ).fetchone()
            state = GameState.model_validate_json(snapshot["state"])
        return StoredCampaign(
            campaign_id=campaign_id,
            adventure=Adventure.model_validate_json(campaign["adventure_copy"]),
            initial_state=initial,
            turns=[self._turn(row) for row in rows],
            state=state,
        )

    def list_campaigns(self) -> list[CampaignSummary]:
        rows = self._db.execute(
            """
            select c.campaign_id, c.adventure_id, c.title, c.created_at,
                   count(t.turn_id) as turns,
                   coalesce((select json_extract(s.state, '$.outcome') from snapshots s
                             join turns lt on lt.turn_id = s.turn_id
                             where lt.campaign_id = c.campaign_id
                               and lt.superseded_at is null
                             order by lt.turn_number desc limit 1),
                            json_extract(c.initial_state, '$.outcome')) as outcome
            from campaigns c
            left join turns t on t.campaign_id = c.campaign_id and t.superseded_at is null
            group by c.campaign_id order by c.campaign_id
            """
        ).fetchall()
        return [CampaignSummary(**dict(row)) for row in rows]

    def rewind(self, campaign_id: int, to_turn: int) -> None:
        self._campaign_row(campaign_id)
        with self._db:
            self._db.execute(
                "update turns set superseded_at = ? where campaign_id = ? and turn_number > ?"
                " and superseded_at is null",
                (_now(), campaign_id, to_turn),
            )

    def turn_log(
        self, campaign_id: int, fallback_only: bool = False, rejected_only: bool = False
    ) -> list[LoggedTurn]:
        """Every turn ever played in the campaign, superseded ones included, in the
        order played. fallback_only: ability-check fallback turns (plan 3.7), the
        mechanics worth building next. rejected_only: turns whose intent failed
        validation twice."""
        self._campaign_row(campaign_id)
        where = ["campaign_id = ?"]
        if fallback_only:
            where.append("fallback = 1")
        if rejected_only:
            where.append("validation_error is not null")
        rows = self._db.execute(
            f"select * from turns where {' and '.join(where)} order by turn_id", (campaign_id,)
        ).fetchall()
        logged = []
        for row in rows:
            turn = self._turn(row)
            logged.append(LoggedTurn(**dict(turn), superseded=row["superseded_at"] is not None))
        return logged

    def _campaign_row(self, campaign_id: int) -> sqlite3.Row:
        row = self._db.execute(
            "select * from campaigns where campaign_id = ?", (campaign_id,)
        ).fetchone()
        if row is None:
            raise UnknownCampaign(f"No campaign {campaign_id}. List them with: solo-dm campaigns")
        return row

    def _turn(self, row: sqlite3.Row) -> TurnRecord:
        events = [
            event_from_stored(e["event_type"], json.loads(e["payload"]))
            for e in self._db.execute(
                "select event_type, payload from events where turn_id = ? order by sequence",
                (row["turn_id"],),
            )
        ]
        return TurnRecord(
            turn_number=row["turn_number"],
            actor_id=row["actor_id"],
            player_id=row["player_id"],
            player_input=row["player_input"],
            intent=Intent.model_validate_json(row["intent"]) if row["intent"] else None,
            validation_error=row["validation_error"],
            events=events,
            narration=row["narration"],
            fallback=bool(row["fallback"]),
            compound=bool(row["compound"]),
            flag_note=row["flag_note"],
        )
