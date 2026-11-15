import shutil
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent.parent
TEST_BOOK = ROOT / "evals" / "millers_cellar"
GOLD = TEST_BOOK / "gold"
SRD = ROOT / "srd"


class Folder:
    """A copy of the test book's gold adventure to break one thing in."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self, name: str):
        return yaml.safe_load((self.path / name).read_text())

    def write(self, name: str, data) -> None:
        (self.path / name).write_text(yaml.safe_dump(data, sort_keys=False))

    def edit(self, name: str, change) -> None:
        data = self.read(name)
        change(data)
        self.write(name, data)


@pytest.fixture
def gold(tmp_path) -> Folder:
    shutil.copytree(GOLD, tmp_path / "millers_cellar")
    return Folder(tmp_path / "millers_cellar")


# The gold Revenge of Azzinax, in dnd-adventures cloned next to this repo.
AZZINAX = ROOT.parent / "dnd-adventures" / "revenge_of_azzinax"
needs_azzinax = pytest.mark.skipif(not AZZINAX.is_dir(),
                                   reason="dnd-adventures is not cloned next to this repo")

# The gold split into the stage files the converter's skills write.
STAGES = TEST_BOOK / "stages"


@pytest.fixture
def stages(tmp_path) -> Folder:
    shutil.copytree(STAGES, tmp_path / "stages")
    return Folder(tmp_path / "stages")


def load_adventure(path: Path):
    from solo_dm.core.adventure.schema import Adventure
    return Adventure.model_validate(yaml.safe_load(path.read_text()))
