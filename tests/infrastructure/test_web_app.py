"""The web app (M6): a thin FastHTML adapter over the same session as the terminal."""

import re
from html.parser import HTMLParser

import pytest
from starlette.testclient import TestClient

from solo_dm.composition_root import build_web_app
from solo_dm.infrastructure.llm.fake_llm import FakeLLM
from solo_dm.infrastructure.persistence.sqlite_campaign_store import SQLiteCampaignStore
from tests.playthroughs.test_campaigns import open_game, run


@pytest.fixture
def store(tmp_path):
    return SQLiteCampaignStore(tmp_path / "campaigns.db")


def web(tmp_path, seed=0):
    app = build_web_app(campaigns=tmp_path / "campaigns.db", llm=lambda campaign_id: FakeLLM(),
                        seed=seed)
    return TestClient(app)


def test_a_campaign_started_in_the_terminal_resumes_in_the_web_app(tmp_path, store):
    game, _ = open_game(store)
    run(game, ["go north", "quit"])
    campaign_id = game.session.campaign_id
    client = web(tmp_path)

    listing = client.get("/campaigns")
    assert listing.status_code == 200
    assert f'href="/play/{campaign_id}"' in listing.text

    page = client.get(f"/play/{campaign_id}")
    assert "go north" in page.text and "Pillared Hall" in page.text

    turn = client.post(f"/play/{campaign_id}", data={"line": "go east"})
    assert turn.status_code == 200
    assert "Guard Room" in turn.text
    resumed = SQLiteCampaignStore(tmp_path / "campaigns.db").load(campaign_id)
    assert [t.player_input for t in resumed.turns] == ["go north", "go east"]


HTMX = {"HX-Request": "true"}


def oob_ids(html: str) -> set[str]:
    """Ids of the elements htmx swaps out of band."""
    found = set()

    class Parser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get("hx-swap-oob") == "true":
                found.add(attrs.get("id"))

    Parser().feed(html)
    return found


def test_an_htmx_turn_returns_the_new_entry_and_swaps_the_room_and_buttons(tmp_path, store):
    game, _ = open_game(store)
    run(game, ["quit"])
    client = web(tmp_path)

    fragment = client.post(f"/play/{game.session.campaign_id}", data={"line": "n"},
                           headers=HTMX).text
    assert "<html" not in fragment
    assert "go north" in fragment  # the shortcut, expanded as in the terminal
    assert oob_ids(fragment) == {"room", "controls"}
    assert "Pillared Hall" in fragment
    assert "go east" in fragment  # a button for the hall's exit east


def test_only_the_static_folder_is_served_and_nothing_loads_from_a_cdn(tmp_path):
    # fast_app() would serve settings.yaml and, through "..", files outside the
    # project (_FASTHTML lesson 6, measured 2026-11-14).
    client = web(tmp_path)
    assert client.get("/static/vendor/htmx.min.js").status_code == 200
    assert client.get("/settings.yaml").status_code == 404
    assert client.get("/adventures/core_five_rooms/adventure.yaml").status_code == 404
    assert client.get("/static/%2e%2e/settings.yaml").status_code == 404
    home = client.get("/").text
    assert "/static/vendor/htmx.min.js" in home and "jsdelivr" not in home


def test_a_new_game_started_on_the_phone_is_a_campaign_the_terminal_can_resume(tmp_path):
    client = web(tmp_path)
    started = client.post("/campaigns", data={"adventure": "core_five_rooms"},
                          follow_redirects=False)
    assert started.status_code == 303
    campaign_id = int(started.headers["location"].rsplit("/", 1)[1])
    client.post(f"/play/{campaign_id}", data={"line": "go north"}, headers=HTMX)

    store = SQLiteCampaignStore(tmp_path / "campaigns.db")
    game, _ = open_game(store, campaign_id)
    assert game.session.state.party_location == "hall"
    assert [t.player_input for t in game.session.turns] == ["go north"]


def test_only_a_listed_adventure_can_be_started(tmp_path):
    client = web(tmp_path)
    client.post("/campaigns", data={"adventure": "../settings"})
    assert SQLiteCampaignStore(tmp_path / "campaigns.db").list_campaigns() == []


class NoModel(FakeLLM):
    def interpret(self, *args, **kwargs):
        raise AssertionError("a built-in command reached the model")


def test_built_in_commands_are_answered_without_the_model_or_a_turn(tmp_path, store):
    game, _ = open_game(store)
    run(game, ["go north", "quit"])
    campaign_id = game.session.campaign_id
    client = TestClient(build_web_app(campaigns=tmp_path / "campaigns.db",
                                      llm=lambda campaign_id: NoModel()))
    answers = {line: client.post(f"/play/{campaign_id}", data={"line": line},
                                 headers=HTMX).text
               for line in ("i", "hp", "look", "map", "help", "flag too vague")}
    assert "Chain Mail" in answers["i"] and "Greatsword" in answers["i"]
    assert "Fighter: 12/12 HP" in answers["hp"]
    assert "Four cracked pillars" in answers["look"]
    assert "<svg" in answers["map"] and "Pillared Hall" in answers["map"]
    assert "Flagged the last turn." in answers["flag too vague"]
    stored = SQLiteCampaignStore(tmp_path / "campaigns.db")
    assert [t.flag_note for t in stored.load(campaign_id).turns] == ["too vague"]


def test_an_unreachable_model_costs_a_retry_and_no_turn(tmp_path, store):
    from solo_dm.infrastructure.llm.cost_log import LLMUnavailable

    class Unreachable(FakeLLM):
        def interpret(self, *args, **kwargs):
            raise LLMUnavailable("broker unreachable")

    game, _ = open_game(store)
    run(game, ["quit"])
    client = TestClient(build_web_app(campaigns=tmp_path / "campaigns.db",
                                      llm=lambda campaign_id: Unreachable()))
    answer = client.post(f"/play/{game.session.campaign_id}", data={"line": "go north"},
                         headers=HTMX).text
    assert "broker unreachable" in answer and "try again" in answer
    assert SQLiteCampaignStore(tmp_path / "campaigns.db").load(
        game.session.campaign_id).turns == []


def test_the_character_sheet_shows_abilities_armour_and_weapons(tmp_path, store):
    game, _ = open_game(store)
    run(game, ["quit"])
    sheet = web(tmp_path).get(f"/character/{game.session.campaign_id}").text
    assert "STR" in sheet and "Armour class: 17 (Chain Mail)" in sheet
    assert "Greatsword: 2d6 slashing" in sheet
    assert "Hit points: 12 / 12" in sheet


def test_the_landing_page_offers_to_continue_the_latest_campaign(tmp_path, store):
    client = web(tmp_path)
    assert "Continue" not in client.get("/").text
    game, _ = open_game(store)
    run(game, ["quit"])
    home = client.get("/").text
    assert f'href="/play/{game.session.campaign_id}"' in home
    assert 'href="/campaigns"' in home and 'href="/cost"' in home


def test_an_unknown_campaign_says_so(tmp_path):
    page = web(tmp_path).get("/play/99")
    assert page.status_code == 404 and "no campaign 99" in page.text


def test_starting_the_app_writes_no_session_key_file(tmp_path, monkeypatch):
    # FastHTML writes .sesskey into the working directory unless given a key; in
    # the container that directory is read-only to the app (_DEPLOY_FASTHTML).
    monkeypatch.chdir(tmp_path)
    web(tmp_path)
    assert not (tmp_path / ".sesskey").exists()


def test_a_post_from_another_site_is_refused_and_plays_no_turn(tmp_path, store):
    # CSRF: a page on another site, opened while on the tailnet, must not be able
    # to play turns (and spend on the API key). Browsers mark such requests.
    game, _ = open_game(store)
    run(game, ["quit"])
    client = web(tmp_path)
    url = f"/play/{game.session.campaign_id}"
    refused = client.post(url, data={"line": "go north"},
                          headers={"Sec-Fetch-Site": "cross-site"})
    assert refused.status_code == 403
    assert client.post("/campaigns", data={"adventure": "core_five_rooms"},
                       headers={"Sec-Fetch-Site": "same-site"}).status_code == 403
    assert client.post(url, data={"line": "go north"},
                       headers={**HTMX, "Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert [t.player_input for t in store.load(game.session.campaign_id).turns] == ["go north"]


def combat_bar(html: str) -> str | None:
    """The text of the bar that stays above the input during a fight."""
    bar = re.search(r'<div class="combat-bar[^"]*">(.*?)</div>', html, re.S)
    return re.sub(r"<[^>]+>|\s+", " ", bar.group(1)).strip() if bar else None


def test_in_a_fight_the_heros_hit_points_stay_above_the_input(tmp_path, store):
    # Jelle's phone play test, 2026-11-14: "I want the hp of my hero to be always
    # visible when in a fight."
    game, _ = open_game(store)
    run(game, ["go north", "quit"])
    client = web(tmp_path)
    url = f"/play/{game.session.campaign_id}"
    assert combat_bar(client.get(url).text) is None
    fight = client.post(url, data={"line": "go east"}, headers=HTMX).text
    hp = SQLiteCampaignStore(tmp_path / "campaigns.db").load(
        game.session.campaign_id).state.party["hero"].hp
    assert combat_bar(fight).startswith(f"Fighter {hp}/12 HP")
    assert combat_bar(client.get(url).text).startswith(f"Fighter {hp}/12 HP")


def test_carried_items_get_a_use_button(tmp_path, store):
    game, _ = open_game(store, adventure_id="scenarios/fountain_and_potion")
    run(game, ["take potion", "quit"])
    fragment = web(tmp_path).post(f"/play/{game.session.campaign_id}",
                                  data={"line": "look"}, headers=HTMX).text
    assert "use Potion of Healing" in fragment
