"""eval: a conversion against its gold, field by field (BUILD_PLAN M8). Each
field is a set of facts; precision is the share of the conversion's facts that
are in the gold, recall the share of the gold's facts the conversion found. They
tell whether a change to a skill made conversions better or worse."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

from solo_dm.core.adventure.map_schema import AdventureMap
from solo_dm.core.adventure.schema import Adventure, ItemPlacement, Lock
from solo_dm.core.state.models import CreatureStatBlock


@dataclass(frozen=True)
class Score:
    precision: float
    recall: float
    missing: list[str]  # in the gold, not in the conversion
    extra: list[str]  # in the conversion, not in the gold


def score(conversion: Counter, gold: Counter) -> Score:
    right = sum((conversion & gold).values())
    return Score(
        precision=right / sum(conversion.values()) if conversion else float(not gold),
        recall=right / sum(gold.values()) if gold else 1.0,
        missing=sorted((gold - conversion).elements()),
        extra=sorted((conversion - gold).elements()),
    )


def evaluate(conversion: Path, gold: Path) -> dict[str, Score]:
    ours, theirs = adventure_facts(conversion), adventure_facts(gold)
    report = {name: score(ours[name], theirs[name]) for name in theirs}
    if (gold / "map.yaml").is_file():
        ours, theirs = map_facts(conversion / "map.yaml"), map_facts(gold / "map.yaml")
        report |= {name: score(ours[name], theirs[name]) for name in theirs}
    return report


def adventure_facts(folder: Path) -> dict[str, Counter]:
    """The facts each field is scored on. Ids a converter chooses freely (items,
    flags, checks, creatures) are left out; places and exits follow the map
    convention, so their ids are compared."""
    adventure = Adventure.model_validate(yaml.safe_load((folder / "adventure.yaml").read_text()))
    where = {e.id: e.location for e in adventure.entities}
    keys = {lock.key for lock in adventure.locks}
    win = adventure.win_condition.flag

    def item(i: ItemPlacement) -> str:
        if i.coins is not None:
            what = str(i.coins)
        elif i.weapon is not None:
            what = f"a weapon ({i.weapon.damage_dice} {i.weapon.damage_type})"
        elif i.effect is not None:
            what = f"healing {i.effect.heal}"
        elif i.id in keys:
            what = "a key"
        elif i.on_take is not None and i.on_take.set_flag == win:
            what = "the goal"
        else:
            what = "an item"
        carrier = where.get(i.carried_by or "", "the party")
        place = i.location if i.location else f"a creature in {carrier}"
        hidden = f", hidden DC {i.hidden.dc}" if i.hidden else ""
        guard = (", one of a choice" if i.requires.not_flags else "") + (
            ", only after something" if i.requires.flags or i.requires.defeated else "")
        return f"{what} in {place}{hidden}{guard}"

    def lock(lock: Lock) -> list[str]:
        ways = [("a key" if lock.key else None),
                (f"pick DC {lock.pick_dc}" if lock.pick_dc else None),
                (f"force DC {lock.force_dc}" if lock.force_dc else None),
                ("a flag" if lock.opens_on_flag else None)]
        return [f"{lock.exit}: {way}" for way in ways if way]

    def check(c, at: str) -> str:
        skill = f" ({c.skill})" if c.skill else ""
        fact = f"{c.ability}{skill} DC {c.dc} at {at}"
        if c.requires.defeated:
            fact += f", after defeating {len(c.requires.defeated)}"
        if c.retry_dc is not None:
            fact += f", retry DC {c.retry_dc}"
        if c.on_failure is not None:
            fact += f", {c.on_failure.damage_dice} {c.on_failure.damage_type} on failure"
        if c.on_success.move_to is not None:
            fact += f", moves to {c.on_success.move_to}"
        return fact

    def hazard(h, at: str) -> str:
        effects = [f"{h.damage_dice} {h.damage_type}" if h.damage_dice else None, h.condition]
        hidden = f", hidden DC {h.hidden.dc}" if h.hidden else ""
        effect = " and ".join(e for e in effects if e)
        return f"{h.save.ability} save DC {h.save.dc}, {effect} in {at}{hidden}"

    checks = [(c, loc.id) for loc in adventure.locations for c in loc.checks]
    checks += [(c, e.location) for e in adventure.entities for c in e.checks]
    goal = [f"a check at {at}" for c, at in checks if c.on_success.set_flag == win]
    goal += [f"taking an item in {i.location or where.get(i.carried_by)}"
             for i in adventure.items if i.on_take and i.on_take.set_flag == win]
    goal += [f"a use at {loc.id}" for loc in adventure.locations for u in loc.uses
             if u.set_flag == win]
    goal += [f"arriving in {loc.id}" for loc in adventure.locations for e in loc.on_enter
             if e.set_flag == win]
    blocks = [CreatureStatBlock.model_validate(yaml.safe_load(p.read_text()))
              for p in sorted((folder / "creatures").glob("*.yaml"))]
    return {
        "locations": Counter(loc.id for loc in adventure.locations),
        "links": Counter(f"{loc.id} -> {e.to}{' through a door' if e.door else ''}"
                         for loc in adventure.locations for e in loc.exits),
        "monsters": Counter(f"{e.srd_ref} in {e.location}" for e in adventure.entities),
        "items": Counter(item(i) for i in adventure.items),
        "locks": Counter(fact for x in adventure.locks for fact in lock(x)),
        "checks": Counter(check(c, at) for c, at in checks),
        "hazards": Counter(hazard(h, loc.id) for loc in adventure.locations
                           for h in loc.hazards),
        "goal": Counter(goal),
        "stat blocks": Counter(
            f"{b.name}: AC {b.armor_class}, HP {b.hit_points}, "
            + ", ".join(f"{a.name} +{a.attack_bonus} {a.damage_dice}" for a in b.attacks)
            for b in blocks),
    }


def map_facts(path: Path) -> dict[str, Counter]:
    if not path.is_file():
        return {"map places": Counter(), "map openings": Counter()}
    adventure_map = AdventureMap.model_validate(yaml.safe_load(path.read_text()))
    places = {**adventure_map.locations, **adventure_map.off_map}
    return {
        "map places": Counter(list(places)),
        "map openings": Counter(f"{o.id} {o.kind} meets {o.meets}"
                                for place in places.values() for o in place.openings),
    }


def render(conversion: Path, gold: Path, report: dict[str, Score]) -> str:
    """The eval report as Markdown: the table, then what was missed or added."""
    lines = [f"# Eval: {conversion.name} against {gold}", "",
             "Precision: the share of the conversion's facts that are in the gold. "
             "Recall: the share of the gold's facts the conversion found.", "",
             "| field | precision | recall | missing | extra |", "|---|---|---|---|---|"]
    lines += [f"| {name} | {s.precision:.2f} | {s.recall:.2f} | {len(s.missing)} | {len(s.extra)} |"
              for name, s in report.items()]
    for name, s in report.items():
        if s.missing or s.extra:
            lines += ["", f"## {name}", ""]
            lines += [f"- missing: {fact}" for fact in s.missing]
            lines += [f"- extra: {fact}" for fact in s.extra]
    return "\n".join(lines) + "\n"
