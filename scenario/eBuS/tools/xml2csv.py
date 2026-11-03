import logging
import os
import subprocess
import sys
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)


def xml2csv(run_dirs: Iterable[Path], max_workers: int = 1) -> None:
    """
    Convert the XML output files of every given seed run directory to CSV
    using SUMO's xml2csv.py (SUMO_HOME/tools/xml/xml2csv.py).
    fcdinfo files are skipped. Conversions run in parallel on max_workers
    threads.
    """
    xml2csv_script = Path(os.environ["SUMO_HOME"]) / "tools" / "xml" / "xml2csv.py"

    xml_files = [
        xml_file
        for run_dir in run_dirs
        for xml_file in Path(run_dir).rglob("*.xml")
        if not xml_file.name.endswith("fcdinfo.xml")
    ]

    def convert(xml_file: Path) -> Path:
        subprocess.run(
            [sys.executable, str(xml2csv_script), str(xml_file)],
            check=True,
            capture_output=True,
            text=True,
        )
        return xml_file

    logger.info("Converting %d XML files to CSV with %d worker(s)", len(xml_files), max_workers)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(convert, f): f for f in xml_files}
        for future in as_completed(futures):
            xml_file = futures[future]
            try:
                future.result()
                logger.info("Converted %s", xml_file)
            except subprocess.CalledProcessError as e:
                logger.error("xml2csv failed for %s: %s", xml_file, e.stderr)
                raise
