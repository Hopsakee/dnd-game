"""Entry point: wires adapters into core services and runs a command."""

import argparse
import os
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from rich.console import Console

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.ports import DicePort, LLMPort
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
from solo_dm.infrastructure.settings import anthropic_connection, load_settings
from solo_dm.infrastructure.srd.yaml_srd_catalog import YamlSrdCatalog
from solo_dm.infrastructure.terminal.terminal_game import TerminalGame

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLO_ACTOR = "hero"
NOT_BUILT_YET = {"web": "M6 (web app)"}


def build_terminal_game(
    adventure_id: str,
    dice: DicePort,
    llm: LLMPort,
    console: Console,
    root: Path = PROJECT_ROOT,
    spend: Callable[[], float] | None = None,
) -> TerminalGame:
    settings = load_settings(root)
    catalog = YamlSrdCatalog(settings.paths.srd)
    adventure = YamlAdventureSource(settings.paths.adventures).load(adventure_id)
    hero = catalog.premade_character("fighter_level_1", character_id=SOLO_ACTOR, player_id="jelle")
    bestiary = {e.srd_ref: catalog.stat_block(e.srd_ref) for e in adventure.entities}
    state = initial_state(adventure, [hero], bestiary)
    return TerminalGame(GameSession(adventure, state, llm, dice), SOLO_ACTOR, console, spend)


def main(argv: list[str] | None = None, root: Path = PROJECT_ROOT) -> int:
    parser = argparse.ArgumentParser(prog="solo-dm", description="Solo D&D 5e engine.")
    commands = parser.add_subparsers(dest="command", required=True)
    play = commands.add_parser("play", help="play an adventure in the terminal")
    play.add_argument("--adventure", default="core_five_rooms")
    play.add_argument("--seed", type=int, help="seed the dice for a reproducible game")
    play.add_argument("--fake", action="store_true",
                      help="play with the keyword fake model: no network, no cost")
    commands.add_parser("cost", help="print model spend per day and per campaign")
    commands.add_parser("web", help="serve the web app")
    args = parser.parse_args(argv)
    if args.command == "play":
        dice = SeededDice(args.seed) if args.seed is not None else RandomDice()
        console = Console()
        llm, spend = _choose_llm(args, root, console)
        try:
            game = build_terminal_game(args.adventure, dice, llm, console, root, spend)
        except UnknownAdventure as unknown:
            print(unknown, file=sys.stderr)
            return 2
        outcome = game.run(lambda: input("> "))
        console.print(f"[bold]Outcome: {outcome}[/bold]")
        return 0
    if args.command == "cost":
        settings = load_settings(root)
        print(CostLog(settings.paths.llm_call_log).report())
        return 0
    print(f"solo-dm {args.command}: not built yet, arrives in {NOT_BUILT_YET[args.command]}",
          file=sys.stderr)
    return 2


def _choose_llm(args, root: Path, console: Console) -> tuple[LLMPort, Callable[[], float] | None]:
    settings = load_settings(root)
    if args.fake or settings.llm.provider == "fake":
        console.print(
            "[dim](fake model: try 'go north', 'attack goblin', 'search', 'take key')[/dim]"
        )
        return FakeLLM(), None
    connection = anthropic_connection(settings, os.environ)
    # One campaign per run until campaigns are stored (M4).
    campaign = f"{args.adventure}@{datetime.now().isoformat(timespec='seconds')}"
    log = CostLog(settings.paths.llm_call_log, settings.cost.daily_cap_usd)
    llm = AnthropicLLM(make_anthropic_client(connection), settings.llm, log, campaign)
    console.print(f"[dim](model: {settings.llm.model_for('narrator')}; "
                  "type 'cost' for this session's spend)[/dim]")
    return llm, lambda: llm.spent_usd
