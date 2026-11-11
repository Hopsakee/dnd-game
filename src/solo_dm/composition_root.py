"""Entry point: wires adapters into core services and runs a command."""

import argparse
import sys

NOT_BUILT_YET = {
    "play": "M2 (terminal harness)",
    "cost": "M3 (cost logging)",
    "web": "M6 (web app)",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="solo-dm", description="Solo D&D 5e engine.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("play", help="play an adventure in the terminal")
    commands.add_parser("cost", help="print model spend per day and per campaign")
    commands.add_parser("web", help="serve the web app")
    args = parser.parse_args(argv)
    print(f"solo-dm {args.command}: not built yet, arrives in {NOT_BUILT_YET[args.command]}",
          file=sys.stderr)
    return 2
