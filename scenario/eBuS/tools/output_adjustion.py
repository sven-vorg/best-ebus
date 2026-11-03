import argparse
import logging
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "sumo" / "output"


def find_output_files(*run_dirs: str | Path) -> tuple[list[Path], list[Path]]:
    """
    Collect all SUMO output files below run_dirs, split into
    (xml_files, parquet_files).
    """
    xml_files, parquet_files = [], []

    for run_dir in run_dirs:
        for path in Path(run_dir).rglob("*"):
            if path.suffix == ".xml":
                xml_files.append(path)
            elif path.suffix == ".parquet":
                parquet_files.append(path)

    return xml_files, parquet_files


def xml2csv(xml_file: Path) -> Path:
    """Convert one SUMO xml output file to csv (written next to it) using SUMO's xml2csv tool."""
    tool = Path(os.environ["SUMO_HOME"]) / "tools" / "xml" / "xml2csv.py"
    subprocess.run([sys.executable, str(tool), str(xml_file)], check=True)
    return xml_file.with_suffix(".csv")


def adjust_output(*run_dirs: str | Path, max_workers: int | None = None, overwrite: bool = False) -> list[Path]:
    """
    Check the output files in run_dirs: parquet files are left as they
    are, xml files are converted to csv. Already converted xml files
    (csv newer than xml) are skipped unless overwrite is set.
    """
    xml_files, parquet_files = find_output_files(*run_dirs)

    for path in parquet_files:
        logger.info(f"Parquet, nothing to do: {path}")

    to_convert = []
    for path in xml_files:
        csv_file = path.with_suffix(".csv")
        if not overwrite and csv_file.exists() and csv_file.stat().st_mtime >= path.stat().st_mtime:
            logger.info(f"Already converted, skipping: {path}")
        else:
            to_convert.append(path)

    converted = []
    with ThreadPoolExecutor(max_workers=max_workers or os.cpu_count()) as pool:
        futures = {pool.submit(xml2csv, f): f for f in to_convert}
        for future in as_completed(futures):
            try:
                converted.append(future.result())
                logger.info(f"Converted {futures[future]}.")
            except subprocess.CalledProcessError as e:
                logger.error(f"Conversion failed for {futures[future]}: {e}")

    logger.info(
        f"{len(parquet_files)} parquet, {len(xml_files)} xml "
        f"({len(converted)} converted, {len(xml_files) - len(to_convert)} skipped)."
    )
    return converted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Convert SUMO xml output files to csv, leave parquet files as they are.")
    parser.add_argument("run_dirs", nargs="*", default=[DEFAULT_OUTPUT_DIR], help="Output/run directories to search (recursively).")
    parser.add_argument("--max-workers", type=int, default=None, help="Parallel conversions (default: CPU count).")
    parser.add_argument("--overwrite", action="store_true", help="Re-convert xml files that already have an up-to-date csv.")
    args = parser.parse_args()

    adjust_output(*args.run_dirs, max_workers=args.max_workers, overwrite=args.overwrite)
