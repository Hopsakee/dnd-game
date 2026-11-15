"""uv run adventure-ingest <command>: the code the adventure-converter agent
calls through the shell (BUILD_PLAN M8). In the order of a conversion:

  extract <pdf> <folder>          text, pictures and page images, and a report
  schema <stage>                  the JSON schema of a stage file (from the models)
  check <stage> <folder>          one stage file on its own
  assemble <folder>               the stage files into adventure.yaml
  verify <folder>                 the hard gate: is the adventure playable?
  eval <conversion> <gold>        field by field against a gold adventure
"""

import argparse
import json
import sys
from pathlib import Path

from adventure_ingest.assemble import assemble
from adventure_ingest.check import check
from adventure_ingest.evaluate import evaluate, render
from adventure_ingest.stages import STAGES
from adventure_ingest.verify import verify
from solo_dm.core.adventure.map_schema import AdventureMap
from solo_dm.core.adventure.schema import Adventure
from solo_dm.core.state.models import CreatureStatBlock

REPO = Path(__file__).resolve().parents[2]
SCHEMAS = {"map": AdventureMap, **{name: model for name, (_, model) in STAGES.items()},
           "stat-block": CreatureStatBlock, "adventure": Adventure}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="adventure-ingest", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("extract", help="the book's PDF to text and pictures")
    run.add_argument("pdf", type=Path)
    run.add_argument("folder", type=Path, help="where to write; usually <ingest>/extract")
    run = commands.add_parser("schema", help="the JSON schema of a stage file")
    run.add_argument("stage", choices=sorted(SCHEMAS))
    run = commands.add_parser("check", help="one stage file on its own")
    run.add_argument("stage", choices=["map", *STAGES])
    run.add_argument("folder", type=Path)
    run.add_argument("--srd", type=Path, default=REPO / "srd")
    run = commands.add_parser("assemble", help="the stage files into adventure.yaml")
    run.add_argument("folder", type=Path)
    run = commands.add_parser("verify", help="the hard gate: is the adventure playable?")
    run.add_argument("folder", type=Path, help="holds adventure.yaml (and map.yaml, creatures/)")
    run.add_argument("--srd", type=Path, default=REPO / "srd")
    run = commands.add_parser("eval", help="a conversion against its gold, field by field")
    run.add_argument("conversion", type=Path)
    run.add_argument("gold", type=Path)
    args = parser.parse_args(argv)

    if args.command == "extract":
        from adventure_ingest.extract import extract
        from adventure_ingest.extract import render as render_extract

        print(render_extract(args.pdf, extract(args.pdf, args.folder)), end="")
        return 0
    if args.command == "schema":
        print(json.dumps(SCHEMAS[args.stage].model_json_schema(), indent=1))
        return 0
    if args.command == "check":
        return report(f"check {args.stage}", check(args.stage, args.folder, args.srd))
    if args.command == "assemble":
        return report("assemble", assemble(args.folder))
    if args.command == "verify":
        return report("verify", verify(args.folder, args.srd))
    if args.command == "eval":
        text = render(args.conversion, args.gold, evaluate(args.conversion, args.gold))
        (args.conversion / "eval.md").write_text(text)
        print(text, end="")
        return 0
    return 2


def report(step: str, problems: list[str]) -> int:
    if not problems:
        print(f"{step}: passed")
        return 0
    print(f"{step}: {len(problems)} problem(s)")
    print("\n".join(f"- {p}" for p in problems))
    return 1


def run() -> None:
    sys.exit(main())


if __name__ == "__main__":
    run()
