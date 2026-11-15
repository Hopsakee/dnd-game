"""AST-based import contract for solo_dm.core (stand-in for import-linter)."""

import ast
from dataclasses import dataclass
from pathlib import Path

ALLOWED_TOP_LEVEL = {
    "__future__",
    "abc",
    "collections",
    "dataclasses",
    "enum",
    "functools",
    "itertools",
    "math",
    "re",
    "typing",
    "pydantic",
}
ALLOWED_PACKAGE_PREFIX = "solo_dm.core"


@dataclass(frozen=True)
class Violation:
    file: Path
    line: int
    module: str


def _module_name(core_dir: Path, file: Path) -> list[str]:
    relative = file.relative_to(core_dir.parent.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return parts


def _imported_modules(core_dir: Path, file: Path):
    tree = ast.parse(file.read_text(), filename=str(file))
    package = _module_name(core_dir, file)
    if file.name != "__init__.py":
        package = package[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)]
                yield node.lineno, ".".join(base + ([node.module] if node.module else []))
            else:
                yield node.lineno, node.module


def _allowed(module: str) -> bool:
    if module == ALLOWED_PACKAGE_PREFIX or module.startswith(ALLOWED_PACKAGE_PREFIX + "."):
        return True
    return module.split(".")[0] in ALLOWED_TOP_LEVEL


def core_import_violations(core_dir: Path) -> list[Violation]:
    return [
        Violation(file, line, module)
        for file in sorted(core_dir.rglob("*.py"))
        for line, module in _imported_modules(core_dir, file)
        if not _allowed(module)
    ]


def imported_modules(package_dir: Path) -> set[str]:
    """Every module the package's files import, as absolute names (M8: the
    contract between solo_dm and adventure_ingest)."""
    root = package_dir.parent
    found = set()
    for file in sorted(package_dir.rglob("*.py")):
        parts = list(file.relative_to(root).with_suffix("").parts)
        package = parts[:-1]
        tree = ast.parse(file.read_text(), filename=str(file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = package[: len(package) - (node.level - 1)]
                    found.add(".".join(base + ([node.module] if node.module else [])))
                else:
                    found.add(node.module)
    return found
