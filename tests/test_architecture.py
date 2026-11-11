"""The dependency rule (plan 3.1): core imports only pure Python and Pydantic.

import-linter is not in the box's wheel store, so this test enforces the same
contracts as .importlinter with an AST walk. It is an allowlist: a new import in
core fails until it is added here on purpose.
"""

from pathlib import Path

from .solo_dm_architecture import core_import_violations

CORE = Path(__file__).parent.parent / "src" / "solo_dm" / "core"


def test_checker_reports_infrastructure_and_io_imports(tmp_path):
    core = tmp_path / "solo_dm" / "core"
    (core / "rules").mkdir(parents=True)
    (core / "rules" / "bad.py").write_text(
        "import sqlite3\n"
        "from solo_dm.infrastructure.dice import random_dice\n"
        "from ...infrastructure import settings\n"
        "import random\n"
        "from pydantic import BaseModel\n"
        "from solo_dm.core.ports import DicePort\n"
        "from ..ports import RollResult\n"
    )
    violations = core_import_violations(core)
    assert [v.module for v in violations] == [
        "sqlite3",
        "solo_dm.infrastructure.dice",
        "solo_dm.infrastructure",
        "random",
    ]


def test_core_imports_only_pure_python_and_pydantic():
    assert core_import_violations(CORE) == []
