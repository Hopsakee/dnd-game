"""Campaigns (M4): a game is stored as it is played, so it can be stopped,
resumed and rewound."""

import io

import pytest
from rich.console import Console

from solo_dm.composition_root import build_terminal_game
from solo_dm.core.state.apply import apply_events
from solo_dm.infrastructure.dice.seeded_dice import SeededDice
from solo_dm.infrastructure.llm.fake_llm import FakeLLM
from solo_dm.infrastructure.persistence.sqlite_campaign_store import SQLiteCampaignStore
from tests.fakes import ScriptedLLM
from tests.playthroughs.test_playthroughs import CORE_WIN


def run(game, lines):
    remaining = iter(lines)

    def read_line():
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    return game.run(read_line)


def open_game(store, campaign_id=None, adventure_id="core_five_rooms", seed=0):
    output = io.StringIO()
    game = build_terminal_game(
        adventure_id, SeededDice(seed), FakeLLM(), Console(file=output, width=100),
        store=store, campaign_id=campaign_id,
    )
    return game, output


def test_a_campaign_stopped_halfway_resumes_where_it_stopped_and_can_be_won(tmp_path):
    store = SQLiteCampaignStore(tmp_path / "campaigns.db")
    first, _ = open_game(store)
    assert run(first, CORE_WIN[:6] + ["quit"]) == "playing"
    stopped_at = first.session.state

    reopened = SQLiteCampaignStore(tmp_path / "campaigns.db")
    resumed, _ = open_game(reopened, first.session.campaign_id, seed=1)
    assert resumed.session.state == stopped_at
    assert [t.turn_number for t in resumed.session.turns] == [1, 2, 3, 4, 5, 6]
    assert run(resumed, CORE_WIN[6:]) == "won"


def replayed(stored):
    return apply_events(stored.initial_state, [e for t in stored.turns for e in t.events])


def test_replaying_the_stored_events_gives_the_latest_snapshot(tmp_path):
    # Plan 3.4: snapshots are a cache; the event log is the truth.
    store = SQLiteCampaignStore(tmp_path / "campaigns.db")
    game, _ = open_game(store)
    lines = CORE_WIN[:2] + ["take ring", "go west", "search", "search", "go east"] + CORE_WIN[2:]
    assert run(game, lines) == "won"

    stored = SQLiteCampaignStore(tmp_path / "campaigns.db").load(game.session.campaign_id)
    assert {"combat_started", "attack_rolled", "body_searched", "hidden_found",
            "door_unlocked", "adventure_won"} <= {e.type for t in stored.turns for e in t.events}
    assert replayed(stored) == stored.state == game.session.state


def test_rewinding_returns_to_an_earlier_turn_and_play_goes_on_from_there(tmp_path):
    store = SQLiteCampaignStore(tmp_path / "campaigns.db")
    game, _ = open_game(store)
    run(game, ["go north", "take ring", "go east", "attack goblin", "quit"])
    after_turn_2 = SQLiteCampaignStore(tmp_path / "campaigns.db")
    campaign_id = game.session.campaign_id

    store.rewind(campaign_id, to_turn=2)
    resumed, _ = open_game(after_turn_2, campaign_id)
    assert resumed.session.state.party_location == "hall"
    assert resumed.session.state.party["hero"].inventory == ("tarnished_ring",)
    assert not resumed.session.state.in_combat
    assert [t.player_input for t in resumed.session.turns] == ["go north", "take ring"]

    run(resumed, ["go west", "quit"])
    stored = store.load(campaign_id)
    assert [t.turn_number for t in stored.turns] == [1, 2, 3]
    assert stored.turns[-1].player_input == "go west"
    assert replayed(stored) == stored.state


def test_a_rewound_campaign_keeps_the_superseded_turns_for_inspection(tmp_path):
    store = SQLiteCampaignStore(tmp_path / "campaigns.db")
    game, _ = open_game(store)
    run(game, ["go north", "go east", "quit"])
    store.rewind(game.session.campaign_id, to_turn=1)
    resumed, _ = open_game(store, game.session.campaign_id)
    run(resumed, ["go west", "quit"])

    log = store.turn_log(game.session.campaign_id)
    assert [(t.turn_number, t.player_input, t.superseded) for t in log] == [
        (1, "go north", False), (2, "go east", True), (2, "go west", False)]


def test_the_turn_log_lists_fallback_turns(tmp_path):
    store = SQLiteCampaignStore(tmp_path / "campaigns.db")
    game, _ = open_game(store, adventure_id="scenarios/ability_check", seed=6)
    run(game, ["climb the cliff", "look", "persuade the gatekeeper", "quit"])

    fallback = store.turn_log(game.session.campaign_id, fallback_only=True)
    assert [t.player_input for t in fallback] == ["climb the cliff", "persuade the gatekeeper"]


def test_the_turn_log_lists_rejected_intents(tmp_path):
    store = SQLiteCampaignStore(tmp_path / "campaigns.db")
    invalid = {"action": "dance"}
    llm = ScriptedLLM([invalid, invalid, {"action": "move", "target_id": "entrance_to_hall"}])
    game = build_terminal_game("core_five_rooms", SeededDice(0), llm,
                               Console(file=io.StringIO()), store=store)
    run(game, ["dance a jig", "go north", "quit"])

    rejected = store.turn_log(game.session.campaign_id, rejected_only=True)
    assert [t.player_input for t in rejected] == ["dance a jig"]
    assert "dance" in rejected[0].validation_error


def test_save_says_the_campaign_is_stored_after_every_turn(tmp_path):
    game, output = open_game(SQLiteCampaignStore(tmp_path / "campaigns.db"))
    run(game, ["go north", "save", "quit"])
    assert "Saved: campaign 1 is stored after every turn." in output.getvalue()


@pytest.mark.parametrize(("adventure_id", "lines", "seed", "outcome"), [
    ("core_five_rooms", CORE_WIN, 4, "lost"),
    ("scenarios/ability_check",
     ["climb the cliff", "persuade the gatekeeper", "persuade the gatekeeper"], 6, "won"),
])
def test_the_replay_invariant_holds_for_losing_and_for_ability_checks(
    tmp_path, adventure_id, lines, seed, outcome
):
    store = SQLiteCampaignStore(tmp_path / "campaigns.db")
    game, _ = open_game(store, adventure_id=adventure_id, seed=seed)
    assert run(game, lines) == outcome
    stored = store.load(game.session.campaign_id)
    assert replayed(stored) == stored.state == game.session.state
