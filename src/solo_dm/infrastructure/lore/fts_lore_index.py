"""Lore files (lore/*.md with YAML front matter: title, tags) indexed in an
in-memory SQLite FTS5 table (plan 3.8). Built from the files at every start, so
a changed file is picked up the next time the game starts."""

import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

import yaml

from solo_dm.core.ports import LorePort, LoreSnippet

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
QUERY_MATCHES = 2  # full-text hits added for an interpreter's lore_query
# Words that would make every file match a query.
STOPWORDS = frozenset(
    "a an and are as at be by do does did for from has have how i in is it its me my "
    "of on or so that the their them they this to was we what when where which who "
    "why with you your know about".split()
)


class InvalidLoreFile(ValueError):
    pass


def read_lore_file(path: Path) -> LoreSnippet:
    match = FRONT_MATTER.match(path.read_text())
    if not match:
        raise InvalidLoreFile(f"{path}: needs front matter between --- lines (title, tags)")
    meta = yaml.safe_load(match.group(1)) or {}
    if not meta.get("title") or not meta.get("tags"):
        raise InvalidLoreFile(f"{path}: front matter needs a title and a list of tags")
    return LoreSnippet(topic=meta["title"], tags=tuple(meta["tags"]),
                       text=match.group(2).strip())


class FtsLoreIndex(LorePort):
    def __init__(self, lore_dir: Path) -> None:
        self._db = sqlite3.connect(":memory:")
        # porter: "fires" finds "fire", "goblins" finds "goblin".
        self._db.execute(
            "create virtual table lore using fts5(topic, tags, text,"
            " tokenize='porter unicode61')"
        )
        self._snippets = [read_lore_file(p) for p in sorted(lore_dir.glob("*.md"))]
        self._db.executemany(
            "insert into lore (rowid, topic, tags, text) values (?, ?, ?, ?)",
            [(n, s.topic, " ".join(s.tags), s.text) for n, s in enumerate(self._snippets)],
        )

    def search(self, query: str | None = None, tags: Iterable[str] = ()) -> list[LoreSnippet]:
        wanted = set(tags)
        found = [s for s in self._snippets if wanted & set(s.tags)]
        for snippet in self._matches(query) if query else []:
            if snippet not in found:
                found.append(snippet)
        return found

    def _matches(self, query: str) -> list[LoreSnippet]:
        # Any of the words, as quoted terms, so the player's punctuation is never
        # read as FTS5 syntax.
        words = [w for w in re.findall(r"\w+", query.lower()) if w not in STOPWORDS]
        if not words:
            return []
        rows = self._db.execute(
            "select rowid from lore where lore match ? order by bm25(lore) limit ?",
            (" OR ".join(f'"{w}"' for w in words), QUERY_MATCHES),
        ).fetchall()
        return [self._snippets[rowid] for (rowid,) in rows]
