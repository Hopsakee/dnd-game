"""M8: adventure_ingest may import the engine's adventure schema (and the models
it uses) and nothing else from solo_dm; solo_dm never imports adventure_ingest."""

from pathlib import Path

from .solo_dm_architecture import imported_modules

SRC = Path(__file__).parent.parent / "src"
ALLOWED_FROM_SOLO_DM = ("solo_dm.core.adventure", "solo_dm.core.state.models")


def test_ingest_imports_only_the_adventure_schema_from_solo_dm():
    from_engine = {module for module in imported_modules(SRC / "adventure_ingest")
                   if module.split(".")[0] == "solo_dm"}
    assert {m for m in from_engine if not m.startswith(ALLOWED_FROM_SOLO_DM)} == set()


def test_solo_dm_never_imports_adventure_ingest():
    assert {m for m in imported_modules(SRC / "solo_dm")
            if m.split(".")[0] == "adventure_ingest"} == set()


def test_the_checker_sees_relative_and_absolute_imports(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "a.py").write_text("from solo_dm.infrastructure import settings\n"
                                  "from . import b\nimport adventure_ingest.cli\n")
    assert imported_modules(package) == {"solo_dm.infrastructure", "pkg", "adventure_ingest.cli"}
