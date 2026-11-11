"""Line-based terminal harness (plan 5.1). Built-in commands are answered by
Python with no model call; everything else is a turn through the pipeline."""

from collections.abc import Callable

from rich.console import Console

from solo_dm.core.turn.session import GameSession

HELP = (
    "Commands: inv, hp, look, map, flag <note>, help, save, quit. "
    "Anything else is an action, e.g. 'go north', 'attack goblin', 'take key'."
)


class TerminalGame:
    def __init__(self, session: GameSession, actor_id: str, console: Console) -> None:
        self.session = session
        self.actor_id = actor_id
        self.console = console

    def run(self, read_line: Callable[[], str]) -> str:
        self.console.print(f"[bold]{self.session.adventure.title}[/bold]")
        self.console.print(self._look())
        while self.session.state.outcome == "playing":
            try:
                line = read_line().strip()
            except EOFError:
                break
            if line and not self.handle(line):
                break
        return self.session.state.outcome

    def handle(self, line: str) -> bool:
        """Answer one input line. Returns False when the player quits."""
        command, _, rest = line.partition(" ")
        builtin = {
            "help": lambda: HELP,
            "inv": self._inventory,
            "hp": self._hit_points,
            "look": self._look,
            "map": self._map,
            "save": lambda: "Saving arrives with campaigns in M4.",
        }
        if command == "quit":
            return False
        if command == "flag":
            self.session.flag_last_turn(rest)
            self.console.print("Flagged the last turn.")
        elif command in builtin and not rest:
            self.console.print(builtin[command]())
        else:
            self.console.print(self.session.play_turn(self.actor_id, line).narration)
        return True

    def _inventory(self) -> str:
        return "\n".join(
            f"{m.name}: " + (", ".join(i.name for i in m.inventory) or "nothing")
            for m in self.session.scene().party
        )

    def _hit_points(self) -> str:
        return "\n".join(f"{m.name}: {m.hp}/{m.max_hp} HP" for m in self.session.scene().party)

    def _look(self) -> str:
        scene = self.session.scene()
        exits = ", ".join(
            f"{e.direction} ({e.leads_to or 'unexplored'}{', locked' if e.locked else ''})"
            for e in scene.exits
        )
        lines = [
            f"[bold]{scene.location_name}[/bold]",
            scene.description.strip(),
            f"Exits: {exits}",
        ]
        if scene.creatures:
            lines.append("Here: " + ", ".join(
                c.name + ("" if c.alive else " (dead)") for c in scene.creatures))
        if scene.items:
            lines.append("Items: " + ", ".join(i.name for i in scene.items))
        return "\n".join(lines)

    def _map(self) -> str:
        state, adventure = self.session.state, self.session.adventure
        lines = []
        for location_id in state.discovered_locations:
            location = adventure.location(location_id)
            links = ", ".join(
                f"{e.direction} -> {adventure.location(e.to).name}"
                for e in location.exits
                if e.to in state.discovered_locations
            )
            marker = "* " if location_id == state.party_location else "  "
            lines.append(f"{marker}{location.name}: {links or 'no known connections'}")
        return "\n".join(lines)
