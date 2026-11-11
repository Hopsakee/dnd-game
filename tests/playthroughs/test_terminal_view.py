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
