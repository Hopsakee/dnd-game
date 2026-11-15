"""Where a creature's stat block is: the adventure's own creatures/ folder
first, then the SRD, as the game loads them."""

from pathlib import Path


def find_stat_block(stat_block_id: str, folder: Path, srd: Path) -> Path | None:
    paths = [folder / "creatures" / f"{stat_block_id}.yaml",
             srd / "creatures" / f"{stat_block_id}.yaml"]
    return next((p for p in paths if p.is_file()), None)
