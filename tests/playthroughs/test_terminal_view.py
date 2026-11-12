"""Terminal harness behaviour found in play-testing (plan 5.1)."""

from tests.playthroughs.test_playthroughs import play


def test_entering_a_room_shows_it_without_look():
    _, _, _, text = play("core_five_rooms", ["go north"])
    after_move = text.split("You enter the Pillared Hall.", 1)[1]
    assert "Four cracked pillars hold up a low ceiling." in after_move
    assert "Exits:" in after_move


def test_a_turn_without_moving_does_not_repeat_the_room():
    _, _, _, text = play("core_five_rooms", ["attack nothing"])
    assert text.count("Damp stone stairs lead down") == 1


def test_a_search_does_not_show_its_dc():
    # The DC differs between "something is hidden here" and "nothing is", so
    # showing it would give the answer away.
    _, _, _, text = play("core_five_rooms", ["search", "go north", "go west", "search"])
    assert "DC" not in text


def _game(llm, spend=None):
    import io

    from rich.console import Console

    from solo_dm.composition_root import build_terminal_game
    from solo_dm.infrastructure.dice.seeded_dice import SeededDice

    output = io.StringIO()
    game = build_terminal_game("core_five_rooms", SeededDice(0), llm,
                               Console(file=output, width=100), spend=spend)
    return game, output


def test_an_unreachable_model_costs_the_player_nothing_but_a_retry():
    from solo_dm.infrastructure.llm.cost_log import LLMUnavailable
    from solo_dm.infrastructure.llm.fake_llm import FakeLLM

    class Unreachable(FakeLLM):
        def interpret(self, *args, **kwargs):
            raise LLMUnavailable("broker unreachable")

    game, output = _game(Unreachable())
    assert game.handle("go north") is True
    assert "broker unreachable" in output.getvalue() and "try again" in output.getvalue()
    assert game.session.state.turn_number == 0 and game.session.turns == []


def test_cost_shows_this_sessions_model_spend():
    from solo_dm.infrastructure.llm.fake_llm import FakeLLM

    game, output = _game(FakeLLM(), spend=lambda: 0.01234)
    game.handle("cost")
    assert "This session: $0.0123" in output.getvalue()


def test_quitting_reports_the_sessions_spend():
    from solo_dm.infrastructure.llm.fake_llm import FakeLLM

    game, output = _game(FakeLLM(), spend=lambda: 0.5)
    game.run(lambda: "quit")
    assert output.getvalue().rstrip().endswith("This session: $0.5000 in model calls.")


def test_with_the_fake_model_there_is_no_spend_to_show():
    from solo_dm.infrastructure.llm.fake_llm import FakeLLM

    game, output = _game(FakeLLM())
    game.handle("cost")
    assert "no model cost" in output.getvalue()
