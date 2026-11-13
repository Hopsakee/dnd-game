"""Line-based terminal harness (plan 5.1). Built-in commands are answered by
Python with no model call; everything else is a turn through the pipeline."""

from collections.abc import Callable

from rich.console import Console

from solo_dm.core.turn.session import GameSession
from solo_dm.infrastructure.llm.cost_log import LLMUnavailable

HELP = (
    "Shortcuts: a = attack, n/s/e/w = go north/south/east/west. "
    "Commands: inv (or inventory, i), hp, look, map, cost, flag <note>, help, save, quit. "
    "Anything else is an action, e.g. 'go north', 'attack goblin', 'search', "
    "'search goblin', 'take key'."
)


# Typed often, so short (play-test flag 10, 2026-11-13). Only the first word is
# expanded: "a goblin" is "attack goblin".
SHORTCUTS = {"a": "attack", "n": "go north", "s": "go south", "e": "go east", "w": "go west"}


def expand_shortcut(line: str) -> str:
    first, _, rest = line.partition(" ")
    if first.lower() not in SHORTCUTS:
        return line
    return f"{SHORTCUTS[first.lower()]} {rest}".strip()


class TerminalGame:
    def __init__(
        self,
        session: GameSession,
        actor_id: str,
        console: Console,
        spend: Callable[[], float] | None = None,
    ) -> None:
        self.session = session
        self.actor_id = actor_id
        self.console = console
        self._spend = spend  # this session's model spend in USD; None with the fake model

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
        if self._spend is not None:
            self.console.print(f"This session: ${self._spend():.4f} in model calls.")
        return self.session.state.outcome

    def handle(self, line: str) -> bool:
        """Answer one input line. Returns False when the player quits."""
        line = expand_shortcut(line)
        command, _, rest = line.partition(" ")
        builtin = {
            "help": lambda: HELP,
            "inv": self._inventory,
            "inventory": self._inventory,
            "i": self._inventory,
            "hp": self._hit_points,
            "look": self._look,
            "map": self._map,
            "save": lambda: "Saving arrives with campaigns in M4.",
            "cost": self._cost,
        }
        if command == "quit":
            return False
        if command == "flag":
            self.session.flag_last_turn(rest)
            self.console.print("Flagged the last turn.")
        elif command in builtin and not rest:
            self.console.print(builtin[command]())
        else:
            location_before = self.session.state.party_location
            try:
                turn = self.session.play_turn(self.actor_id, line)
            except LLMUnavailable as unavailable:
                self.console.print(
                    f"[red]The model could not be reached ({unavailable}). "
                    "Nothing happened; try again.[/red]"
                )
                return True
            self.console.print(turn.narration)
            # Entering a room shows it, from state rather than from the model, so
            # the exits and items are always right whichever model narrates.
            if self.session.state.party_location != location_before:
                self.console.print(self._look())
            # Whose turn it is comes from state too; the narrator keeps mechanics out.
            scene = self.session.scene()
            if scene.in_combat and scene.active_combatant == self.actor_id:
                self.console.print("Your turn.")
        return True

    def _cost(self) -> str:
        if self._spend is None:
            return "The fake model is playing: no model cost."
        return f"This session: ${self._spend():.4f} in model calls. All time: uv run solo-dm cost"

    def _inventory(self) -> str:
        lines = []
        for m in self.session.scene().party:
            gear = [f"wears {m.armor} (AC {m.armor_class})" if m.armor else f"AC {m.armor_class}"]
            if m.weapons:
                gear.append("wields " + ", ".join(m.weapons))
            carried = ", ".join(i.name for i in m.inventory) or "empty"
            lines.append(f"{m.name}: {', '.join(gear)}; pack: {carried}")
        return "\n".join(lines)

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
        if scene.nearby:
            lines.append("Nearby: " + "; ".join(f"{n.direction}: {n.senses}" for n in scene.nearby))
        return "\n".join(lines)

    def _map(self) -> str:
        state, adventure = self.session.state, self.session.adventure
        lines = []
        for location_id in state.discovered_locations:
            location = adventure.location(location_id)
            links = ", ".join(
                f"{e.direction} -> {adventure.location(e.to).name}"
                for e in location.exits
                if e.to in state.discovered_locations and e.id not in state.hidden_unfound
            )
            marker = "* " if location_id == state.party_location else "  "
            lines.append(f"{marker}{location.name}: {links or 'no known connections'}")
        return "\n".join(lines)
