"""Entry point: wires adapters into core services and runs a command."""

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.ports import CampaignStorePort, DicePort, LLMPort
from solo_dm.core.turn.session import GameSession
from solo_dm.infrastructure.adventures.yaml_adventure_source import (
    UnknownAdventure,
    YamlAdventureSource,
)
from solo_dm.infrastructure.dice.random_dice import RandomDice
from solo_dm.infrastructure.dice.seeded_dice import SeededDice
from solo_dm.infrastructure.llm.anthropic_llm import AnthropicLLM, make_anthropic_client
from solo_dm.infrastructure.llm.cost_log import CostLog
from solo_dm.infrastructure.llm.fake_llm import FakeLLM
from solo_dm.infrastructure.lore.fts_lore_index import FtsLoreIndex
from solo_dm.infrastructure.persistence.sqlite_campaign_store import (
    SQLiteCampaignStore,
    UnknownCampaign,
)
from solo_dm.infrastructure.settings import anthropic_connection, load_settings
from solo_dm.infrastructure.srd.yaml_srd_catalog import YamlSrdCatalog
from solo_dm.infrastructure.terminal.terminal_game import TerminalGame

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLO_ACTOR = "hero"
NOT_BUILT_YET = {"web": "M6 (web app)"}
CAMPAIGN_FILE = "campaigns.db"


def build_terminal_game(
    adventure_id: str,
    dice: DicePort,
    llm: LLMPort,
    console: Console,
    root: Path = PROJECT_ROOT,
    spend: Callable[[], float] | None = None,
    store: CampaignStorePort | None = None,
    campaign_id: int | None = None,
) -> TerminalGame:
    """A new game of adventure_id, stored as a new campaign when a store is given;
    or, with campaign_id, that campaign resumed from the store."""
    settings = load_settings(root)
    lore = FtsLoreIndex(settings.paths.lore)
    if store is not None and campaign_id is not None:
        session = GameSession.resume(store, campaign_id, llm, dice, lore)
        return TerminalGame(session, SOLO_ACTOR, console, spend)
    catalog = YamlSrdCatalog(settings.paths.srd)
    adventure = YamlAdventureSource(settings.paths.adventures).load(adventure_id)
    hero = catalog.premade_character("fighter_level_1", character_id=SOLO_ACTOR, player_id="jelle")
    bestiary = {e.srd_ref: catalog.stat_block(e.srd_ref) for e in adventure.entities}
    state = initial_state(adventure, [hero], bestiary)
    if store is None:
        session = GameSession(adventure, state, llm, dice, lore=lore)
    else:
        session = GameSession.start_campaign(store, adventure, state, llm, dice, lore)
    return TerminalGame(session, SOLO_ACTOR, console, spend)


def main(argv: list[str] | None = None, root: Path = PROJECT_ROOT) -> int:
    parser = argparse.ArgumentParser(prog="solo-dm", description="Solo D&D 5e engine.")
    commands = parser.add_subparsers(dest="command", required=True)
    play = commands.add_parser("play", help="play an adventure in the terminal")
    play.add_argument("--adventure", default="core_five_rooms")
    play.add_argument("--campaign", type=int, help="resume this campaign instead of a new one")
    play.add_argument("--seed", type=int, help="seed the dice for a reproducible game")
    play.add_argument("--fake", action="store_true",
                      help="play with the keyword fake model: no network, no cost")
    commands.add_parser("campaigns", help="list the stored campaigns")
    rewind = commands.add_parser("rewind", help="return a campaign to an earlier turn")
    rewind.add_argument("campaign", type=int)
    rewind.add_argument("turn", type=int, help="the last turn to keep (0: the start)")
    turns = commands.add_parser("turns", help="list a campaign's turns, superseded ones too")
    turns.add_argument("campaign", type=int)
    turns.add_argument("--fallback", action="store_true", help="only ability-check fallbacks")
    turns.add_argument("--rejected", action="store_true", help="only rejected intents")
    commands.add_parser("cost", help="print model spend per day and per campaign")
    commands.add_parser("web", help="serve the web app")
    args = parser.parse_args(argv)
    if args.command == "cost":
        settings = load_settings(root)
        print(CostLog(settings.paths.llm_call_log).report())
        return 0
    if args.command == "web":
        print(f"solo-dm {args.command}: not built yet, arrives in {NOT_BUILT_YET[args.command]}",
              file=sys.stderr)
        return 2
    try:
        return {"play": _play, "campaigns": _campaigns, "rewind": _rewind,
                "turns": _turns}[args.command](args, root)
    except (UnknownAdventure, UnknownCampaign) as unknown:
        print(unknown, file=sys.stderr)
        return 2


def campaign_store(root: Path) -> SQLiteCampaignStore:
    return SQLiteCampaignStore(load_settings(root).paths.campaigns / CAMPAIGN_FILE)


def _play(args, root: Path) -> int:
    dice = SeededDice(args.seed) if args.seed is not None else RandomDice()
    console = Console()
    store = campaign_store(root)
    if args.campaign is not None:
        store.load(args.campaign)  # an unknown id fails here, before any model is set up
    llm, spend = _choose_llm(args, root, console)
    game = build_terminal_game(args.adventure, dice, llm, console, root, spend,
                               store=store, campaign_id=args.campaign)
    campaign_id = game.session.campaign_id
    if isinstance(llm, AnthropicLLM):
        llm.campaign = f"campaign {campaign_id}"
    if args.campaign is None:
        console.print(f"[dim]Campaign {campaign_id}: saved after every turn.[/dim]")
    else:
        console.print(f"[dim]Resuming campaign {campaign_id} "
                      f"after turn {len(game.session.turns)}.[/dim]")
    outcome = game.run(lambda: input("> "))
    console.print(f"[bold]Outcome: {outcome}[/bold]")
    if outcome == "playing":
        console.print(f"Resume with: uv run solo-dm play --campaign {campaign_id}")
    return 0


def _campaigns(args, root: Path) -> int:
    campaigns = campaign_store(root).list_campaigns()
    if not campaigns:
        print("No campaigns yet. Start one with: uv run solo-dm play")
    for c in campaigns:
        print(f"{c.campaign_id:>3}  {c.created_at}  {c.title} ({c.adventure_id}), "
              f"{c.turns} turns, {c.outcome}")
    return 0


def _rewind(args, root: Path) -> int:
    campaign_store(root).rewind(args.campaign, args.turn)
    print(f"Campaign {args.campaign} is back after turn {args.turn}; later turns are kept "
          f"as superseded. Resume with: uv run solo-dm play --campaign {args.campaign}")
    return 0


def _turns(args, root: Path) -> int:
    log = campaign_store(root).turn_log(args.campaign, args.fallback, args.rejected)
    for t in log:
        marks = [m for m, on in (("superseded", t.superseded), ("fallback", t.fallback),
                                 ("rejected", t.validation_error is not None),
                                 (f"flag: {t.flag_note}", t.flag_note)) if on]
        action = t.intent.action if t.intent else "-"
        print(f"{t.turn_number:>3}  {t.player_input!r} -> {action}"
              + (f"  [{'; '.join(marks)}]" if marks else ""))
    if not log:
        print("No turns.")
    return 0


def _choose_llm(args, root: Path, console: Console) -> tuple[LLMPort, Callable[[], float] | None]:
    settings = load_settings(root)
    if args.fake or settings.llm.provider == "fake":
        console.print(
            "[dim](fake model: try 'go north', 'attack goblin', 'search', 'take key')[/dim]"
        )
        return FakeLLM(), None
    connection = anthropic_connection(settings, os.environ)
    log = CostLog(settings.paths.llm_call_log, settings.cost.daily_cap_usd)
    # The campaign label is set once the campaign exists (see _play).
    llm = AnthropicLLM(make_anthropic_client(connection), settings.llm, log, campaign="")
    console.print(f"[dim](model: {settings.llm.model_for('narrator')}; "
                  "type 'cost' for this session's spend)[/dim]")
    return llm, lambda: llm.spent_usd
