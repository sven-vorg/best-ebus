#!/usr/bin/env python
__author__ = "Sven Vorgheim"
__license__ = "GPL v2 or later (In accoardance to SUMO)"
__maintainer__ = "Sven Vorgheim"
__email__ = "sven.vorgheim@fu-berlin.de"
__status__ = "Prototype"
__date__ = "02.07.2026"

import os
import glob
import dotenv
from pathlib import Path

from preprocessing.heuristic_preprocessing import HeuristicPreprocessing
from postprocessing.heuristic_postprocessing import HeuristicPostprocessing
from database.db_ebus import DBeBuS
from visualisation import dashboard

PROJECT_ROOT = Path(__file__).resolve().parent

class EbusMain():
    def __init__(self):
        pass

    def run_heruistic_preprocessing(self):
        #hp = HeuristicPreprocessing()
        #hp.main()
        pass

    def run_heruistic_postprocessing(self):
        #hp = HeuristicPostprocessing()
        #hp.main()
        pass

    def update_database(self):
        DBeBuS()

    # Env Helpers
    def get_latest_runtime(self, path, *paths) -> str | None:
        """Returns the name of the latest (most recent) file 
        of the joined path(s)"""
        fullpath = os.path.join(path, *paths)
        list_of_files = glob.glob(fullpath)  # You may use iglob in Python3
        if not list_of_files:
            print("No files found.")           # I prefer using the negation
            return None                     # because it behaves like a shortcut
        latest_file = max(list_of_files, key=os.path.getctime)
        _, filename = os.path.split(latest_file)
        time = filename.split("_")[2]
        return time

    def set_latest_runtime(self, timestamp: str):
        dotenv.set_key(dotenv.find_dotenv(),"latest_timestamp", timestamp)
        print("Timestamp latest runtime set.")

    def produce_dashboard(self, db_path: Path):
            app = dashboard.App(db_path)
            app.mainloop()

    def main(self):
        pass


if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent

    SUMO_OUTPUT_PATH: Path = Path(HERE.parent / "sumo/output/")

    eb = EbusMain()
    timestamp = eb.get_latest_runtime(SUMO_OUTPUT_PATH, "*")
    if timestamp is not None:
        print(f"Latest runtime: {timestamp}")
        eb.set_latest_runtime(timestamp)
    eb.update_database()
    eb.produce_dashboard(db_path=Path(HERE /"database/ebus.db"))
    pass