import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SEED_FILE_PATTERN = re.compile(r"^(\d+)_multirun_.+\.xml$")


def order_output(output_dir: Path) -> Path:
    """
    Move all output files from a multi-seed SUMO run (named
    "<seed>_multirun_<type>.xml", see EBusMain.run_simulation_seeds)
    into per-seed "<seed>_directory" folders, grouped together under
    one run_<timestamp> folder so a run's seeds stay together.
    """
    output_dir = Path(output_dir)

    seeds = sorted(
        {
            match.group(1)
            for path in output_dir.glob("*_multirun_*.xml")
            if (match := SEED_FILE_PATTERN.match(path.name))
        },
        key=int,
    )

    if not seeds:
        raise FileNotFoundError(f"No multi-seed run output found in {output_dir}")

    run_dir = output_dir / f"run_{datetime.now():%Y-%m-%d-%H-%M-%S}"
    run_dir.mkdir(exist_ok=True)

    for seed in seeds:
        seed_dir = run_dir / f"{seed}_directory"
        seed_dir.mkdir(exist_ok=True)

        for path in output_dir.glob(f"{seed}_multirun_*.xml"):
            shutil.move(str(path), seed_dir / path.name)

        logger.info(f"Seed {seed} output moved to {seed_dir}")

    logger.info(f"Run output moved to {run_dir}")
    return run_dir
