"""The web app (plan 5.2): a thin FastHTML + htmx adapter over GameSession. No
game logic here: turns go through the same session as the terminal, and every
screen is drawn from the session's scene and state.

Built with FastHTML(), never fast_app(): fast_app() always adds a route that
serves any .yaml/.txt/... file under the working directory, `..` included
(_FASTHTML skill, lesson 6). Only static/ is served, through Starlette's
StaticFiles, which refuses paths that leave it. htmx and fasthtml.js are
vendored there, so the pages load nothing from a CDN."""

import json
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fasthtml.common import (
    H1,
    H2,
    A,
    Button,
    Details,
    Div,
    FastHTML,
    Form,
    FtResponse,
    Input,
    Li,
    Link,
    Main,
    Meta,
    Nav,
    Option,
    P,
    Pre,
    Script,
    Select,
    Span,
    Summary,
    Table,
    Td,
    Th,
    Title,
    Tr,
    Ul,
)
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from solo_dm.core.ports import CampaignSummary
from solo_dm.core.turn.player_view import expand_shortcut
from solo_dm.core.turn.scene import SceneContext
from solo_dm.core.turn.session import GameSession, TurnRecord
from solo_dm.infrastructure.llm.cost_log import LLMUnavailable
from solo_dm.infrastructure.persistence.sqlite_campaign_store import UnknownCampaign
from solo_dm.infrastructure.web.map_svg import map_svg

HELP = (
    "Type what you do, or tap a button. Shortcuts: a = attack, n/s/e/w = go north, "
    "south, east, west. Commands: look, inv, hp, map, help, flag <note> (marks the last "
    "turn as wrong). The game is saved after every turn."
)


SCROLL_DOWN = "window.scrollTo(0, document.body.scrollHeight)"


@dataclass(frozen=True)
class WebServices:
    """What the app needs from the composition root."""

    open_session: Callable[[int], GameSession]
    new_session: Callable[[str], GameSession]
    list_campaigns: Callable[[], list[CampaignSummary]]
    adventures: Callable[[], list[str]]
    cost_report: Callable[[], str]
    actor_id: str
    static: Path


def create_web_app(services: WebServices) -> FastHTML:
    app = FastHTML(
        htmx=False, surreal=False, title="solo-dm",
        # The app keeps nothing in the session, so a fresh key per start will do,
        # and FastHTML then writes no .sesskey file into the working directory.
        secret_key=secrets.token_hex(32),
        hdrs=(Meta(name="viewport", content="width=device-width, initial-scale=1"),
              Script(src="/static/vendor/htmx.min.js"),
              Script(src="/static/vendor/fasthtml.js"),
              Link(rel="stylesheet", href="/static/app.css")),
    )
    app.mount("/static", StaticFiles(directory=services.static), name="static")
    turn_locks: dict[int, threading.Lock] = {}
    guard = threading.Lock()

    def lock_for(campaign_id: int) -> threading.Lock:
        # Two taps at once must not both play turn N+1 of the same campaign.
        with guard:
            return turn_locks.setdefault(campaign_id, threading.Lock())

    def session_or_404(campaign_id: int) -> GameSession | None:
        try:
            return services.open_session(campaign_id)
        except UnknownCampaign:
            return None

    @app.get("/")
    def home():
        campaigns = services.list_campaigns()
        playing = [c for c in campaigns if c.outcome == "playing"]
        items = []
        if playing:
            latest = playing[-1]
            items.append(Li(A(f"Continue: {latest.title} (campaign {latest.campaign_id})",
                              href=f"/play/{latest.campaign_id}")))
        items += [Li(A("Campaigns and a new game", href="/campaigns")),
                  Li(A("Model cost", href="/cost"))]
        return page("solo-dm", H1("solo-dm"), Ul(*items, cls="menu"))

    @app.get("/campaigns")
    def campaigns():
        rows = [Li(A(f"{c.title}", href=f"/play/{c.campaign_id}"),
                   Span(f" campaign {c.campaign_id}, {c.turns} turns, {c.outcome}",
                        cls="muted"))
                for c in reversed(services.list_campaigns())]
        new = Form(
            Select(*[Option(a, value=a) for a in services.adventures()], name="adventure"),
            Button("New game"),
            method="post", action="/campaigns", cls="row",
        )
        return page("Campaigns", H1("Campaigns"), new,
                    Ul(*rows, cls="menu") if rows else P("No campaigns yet."))

    @app.post("/campaigns")
    def start(adventure: str):
        if adventure not in services.adventures():
            return page("Unknown adventure", P(f"No adventure {adventure!r}."))
        session = services.new_session(adventure)
        return RedirectResponse(f"/play/{session.campaign_id}", status_code=303)

    @app.get("/play/{campaign_id}")
    def play(campaign_id: int):
        session = session_or_404(campaign_id)
        if session is None:
            return not_found(campaign_id)
        log = [P(session.adventure.title, cls="muted")]
        log += [turn_entry(t) for t in session.turns]
        return page(
            session.adventure.title,
            campaign_nav(campaign_id, "play"),
            room_panel(session.scene()),
            Div(*log, id="log", **{"hx-on::after-settle": SCROLL_DOWN}),
            play_controls(campaign_id, session, services.actor_id),
            Script(SCROLL_DOWN),
        )

    @app.post("/play/{campaign_id}")
    def turn(campaign_id: int, line: str, request: Request):
        with lock_for(campaign_id):
            session = session_or_404(campaign_id)
            if session is None:
                return not_found(campaign_id)
            entries = handle_line(session, services, line.strip())
        if "HX-Request" not in request.headers:  # a plain form post: show the page
            return RedirectResponse(f"/play/{campaign_id}", status_code=303)
        return (*entries,
                room_panel(session.scene(), oob=True),
                play_controls(campaign_id, session, services.actor_id, oob=True))

    @app.get("/character/{campaign_id}")
    def character(campaign_id: int):
        session = session_or_404(campaign_id)
        if session is None:
            return not_found(campaign_id)
        return page("Character", campaign_nav(campaign_id, "character"),
                    *[character_sheet(c) for c in session.state.party.values()])

    @app.get("/inventory/{campaign_id}")
    def inventory(campaign_id: int):
        session = session_or_404(campaign_id)
        if session is None:
            return not_found(campaign_id)
        return page("Inventory", campaign_nav(campaign_id, "inventory"),
                    inventory_view(session.scene()))

    @app.get("/map/{campaign_id}")
    def known_map_page(campaign_id: int):
        session = session_or_404(campaign_id)
        if session is None:
            return not_found(campaign_id)
        return page("Map", campaign_nav(campaign_id, "map"),
                    Div(map_svg(session.state, session.adventure), cls="map"))

    @app.get("/cost")
    def cost():
        return page("Model cost", H1("Model cost"), Pre(services.cost_report()))

    return app


def handle_line(session: GameSession, services: WebServices, line: str) -> list:
    """One input line, as the terminal handles it: built-in commands without the
    model, everything else a turn through the session."""
    if not line:
        return []
    line = expand_shortcut(line)
    command, _, rest = line.partition(" ")
    scene = session.scene()
    builtin = {
        "help": lambda: P(HELP),
        "look": lambda: room_view(scene),
        "inv": lambda: inventory_view(scene),
        "inventory": lambda: inventory_view(scene),
        "i": lambda: inventory_view(scene),
        "hp": lambda: P(", ".join(f"{m.name}: {m.hp}/{m.max_hp} HP" for m in scene.party)),
        "map": lambda: Div(map_svg(session.state, session.adventure), cls="map"),
        "save": lambda: P("Saved: the game is stored after every turn."),
        "quit": lambda: P("The game is stored after every turn; just close the page."),
        "cost": lambda: Pre(services.cost_report()),
    }
    if command == "flag":
        if not session.turns:
            return [info(line, P("There is no turn to flag yet."))]
        session.flag_last_turn(rest)
        return [info(line, P("Flagged the last turn."))]
    if command in builtin and not rest:
        return [info(line, builtin[command]())]
    location_before = session.state.party_location
    try:
        record = session.play_turn(services.actor_id, line)
    except LLMUnavailable as unavailable:
        return [info(line, P(f"The model could not be reached ({unavailable}). "
                             "Nothing happened; try again.", cls="warn"))]
    entries = [turn_entry(record)]
    after = session.scene()
    if session.state.party_location != location_before:
        entries.append(Div(room_view(after), cls="entry room-entry"))
    if after.in_combat and after.active_combatant == services.actor_id:
        entries.append(P("Your turn.", cls="muted"))
    if session.state.outcome != "playing":
        entries.append(P(outcome_text(session.state.outcome), cls="outcome"))
    return entries


def turn_entry(record: TurnRecord):
    return Div(P(record.player_input, cls="you"), P(record.narration, cls="dm"), cls="entry")


def info(line: str, body):
    return Div(P(line, cls="you"), body, cls="entry info")


def outcome_text(outcome: str) -> str:
    return {"won": "You won this adventure.", "lost": "You have fallen. The adventure is lost."
            }.get(outcome, outcome)


def room_view(scene: SceneContext):
    exits = ", ".join(
        f"{e.direction} ({e.leads_to or 'unexplored'}{', locked' if e.locked else ''})"
        for e in scene.exits)
    parts = [P(Span(scene.location_name, cls="room-name")),
             P(scene.description.strip()), P(f"Exits: {exits}")]
    if scene.creatures:
        parts.append(P("Here: " + ", ".join(
            c.name + ("" if c.alive else " (dead)") for c in scene.creatures)))
    if scene.items:
        parts.append(P("Items: " + ", ".join(i.name for i in scene.items)))
    if scene.nearby:
        parts.append(P("Nearby: " + "; ".join(f"{n.direction}: {n.senses}"
                                              for n in scene.nearby)))
    return Div(*parts)


def room_panel(scene: SceneContext, oob: bool = False):
    party = ", ".join(f"{m.name} {m.hp}/{m.max_hp} HP" for m in scene.party)
    return Details(Summary(scene.location_name, Span(f" · {party}", cls="muted")),
                   room_view(scene), id="room", **({"hx_swap_oob": "true"} if oob else {}))


def quick_actions(scene: SceneContext) -> list[str]:
    """Buttons for what can be done here; every one is a line the player could type."""
    actions = [f"go {e.direction}" for e in scene.exits]
    actions += [f"attack {c.name}" for c in scene.creatures
                if c.alive and c.attitude == "hostile"]
    actions += [f"search {c.name}" for c in scene.creatures if not c.alive]
    actions += [f"take {i.name}" for i in scene.items]
    return actions + ["search", "look", "inv", "hp", "map"]


def play_controls(campaign_id: int, session: GameSession, actor_id: str, oob: bool = False):
    extra = {"hx_swap_oob": "true"} if oob else {}
    if session.state.outcome != "playing":
        return Div(P(outcome_text(session.state.outcome), cls="outcome"),
                   A("Back to campaigns", href="/campaigns"), id="controls", **extra)
    target = {"hx_post": f"/play/{campaign_id}", "hx_target": "#log", "hx_swap": "beforeend"}
    buttons = [Button(a, type="button", hx_vals=_vals(a), cls="quick", **target)
               for a in quick_actions(session.scene())]
    form = Form(
        Input(name="line", placeholder="What do you do?", autocomplete="off",
              aria_label="What do you do?"),
        Button("Do it"),
        method="post", action=f"/play/{campaign_id}", cls="row",
        **target, **{"hx-on::after-request": "this.reset()"},
    )
    return Div(Div(*buttons, cls="quick-row"), form, id="controls", cls="controls", **extra)


def _vals(line: str) -> str:
    return json.dumps({"line": line})


def inventory_view(scene: SceneContext):
    blocks = []
    for m in scene.party:
        rows = [Li(f"Wears: {m.armor} (AC {m.armor_class})" if m.armor
                   else f"AC {m.armor_class}, no armour")]
        rows += [Li(f"Wields: {w}") for w in m.weapons]
        pack = [Li(i.name, P(i.description, cls="muted") if i.description else "")
                for i in m.inventory]
        blocks.append(Div(H2(m.name), Ul(*rows), P("Pack:"),
                          Ul(*pack) if pack else P("empty", cls="muted")))
    return Div(*blocks)


def character_sheet(c):
    abilities = Table(
        Tr(*[Th(a) for a in ("STR", "DEX", "CON", "INT", "WIS", "CHA")]),
        Tr(*[Td(f"{getattr(c.abilities, a)} ({_signed(c.abilities.modifier(a))})")
             for a in ("STR", "DEX", "CON", "INT", "WIS", "CHA")]),
        cls="abilities")
    weapons = [Li(f"{w.name}: {w.damage_dice} {w.damage_type} ({w.ability})")
               for w in c.weapons]
    skills = ", ".join(s.replace("_", " ") for s in c.skill_proficiencies) or "none"
    return Div(
        H1(c.name), P(f"Level {c.level}", cls="muted"),
        Ul(Li(f"Hit points: {c.hp} / {c.max_hp}"),
           Li(f"Armour class: {c.armor_class}" + (f" ({c.armor})" if c.armor else "")),
           Li(f"Proficiency bonus: {_signed(c.proficiency_bonus)}"),
           Li(f"Skills: {skills}"),
           *([Li("Conditions: " + ", ".join(c.conditions))] if c.conditions else [])),
        abilities, H2("Weapons"), Ul(*weapons) if weapons else P("none", cls="muted"),
    )


def _signed(n: int) -> str:
    return f"+{n}" if n >= 0 else str(n)


def campaign_nav(campaign_id: int, here: str):
    links = [("play", "Play", f"/play/{campaign_id}"),
             ("character", "Character", f"/character/{campaign_id}"),
             ("inventory", "Inventory", f"/inventory/{campaign_id}"),
             ("map", "Map", f"/map/{campaign_id}")]
    return Nav(*[A(label, href=href, cls="here" if key == here else "")
                 for key, label, href in links], cls="tabs")


def page(title: str, *content):
    menu = Nav(A("Home", href="/"), A("Campaigns", href="/campaigns"), A("Cost", href="/cost"),
               cls="top")
    return Title(f"{title} · solo-dm"), Main(menu, *content)


def not_found(campaign_id: int):
    body = page("No such campaign", H1("No such campaign"),
                P(f"There is no campaign {campaign_id}."), A("Campaigns", href="/campaigns"))
    return FtResponse(body, status_code=404)
