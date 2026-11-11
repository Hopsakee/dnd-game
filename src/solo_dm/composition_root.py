"""Entry point: wires adapters into core services and runs a command."""

import argparse
import sys
from pathlib import Path

from rich.console import Console

from solo_dm.core.adventure.initial_state import initial_state
from solo_dm.core.ports import DicePort, LLMPort
from solo_dm.core.turn.session import GameSession
from solo_dm.infrastructure.adventures.yaml_adventure_source import YamlAdventureSource
from solo_dm.infrastructure.dice.random_dice import RandomDice
from solo_dm.infrastructure.dice.seeded_dice import SeededDice
from solo_dm.infrastructure.llm.fake_llm import FakeLLM
from solo_dm.infrastructure.settings import load_settings
from solo_dm.infrastructure.srd.yaml_srd_catalog import YamlSrdCatalog
from solo_dm.infrastructure.terminal.terminal_game import TerminalGame

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLO_ACTOR = "hero"
NOT_BUILT_YET = {"cost": "M3 (cost logging)", "web": "M6 (web app)"}


def build_terminal_game(
    adventure_id: str, dice: DicePort, llm: LLMPort, console: Console, root: Path = PROJECT_ROOT
) -> TerminalGame:
    settings = load_settings(root)
    catalog = YamlSrdCatalog(settings.paths.srd)
    adventure = YamlAdventureSource(settings.paths.adventures).load(adventure_id)
    hero = catalog.premade_character("fighter_level_1", character_id=SOLO_ACTOR, player_id="jelle")
    bestiary = {e.srd_ref: catalog.stat_block(e.srd_ref) for e in adventure.entities}
    state = initial_state(adventure, [hero], bestiary)
    return TerminalGame(GameSession(adventure, state, llm, dice), SOLO_ACTOR, console)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solo-dm", description="Solo D&D 5e engine.")
    commands = parser.add_subparsers(dest="command", required=True)
    play = commands.add_parser("play", help="play an adventure in the terminal")
    play.add_argument("--adventure", default="core_five_rooms")
    play.add_argument("--seed", type=int, help="seed the dice for a reproducible game")
    commands.add_parser("cost", help="print model spend per day and per campaign")
    commands.add_parser("web", help="serve the web app")
    args = parser.parse_args(argv)
    if args.command == "play":
        dice = SeededDice(args.seed) if args.seed is not None else RandomDice()
        console = Console()
        console.print(
            "[dim](fake model: try 'go north', 'attack goblin', 'search', 'take key')[/dim]"
        )
        outcome = build_terminal_game(args.adventure, dice, FakeLLM(), console).run(
            lambda: input("> ")
        )
        console.print(f"[bold]Outcome: {outcome}[/bold]")
        return 0
    print(f"solo-dm {args.command}: not built yet, arrives in {NOT_BUILT_YET[args.command]}",
          file=sys.stderr)
    return 2
