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

from preprocessing.heuristic_preprocessing import HeuristicPreprocessing
from postprocessing.heuristic_postprocessing import HeuristicPostprocessing
from visualisation import dashboard

class EbusMain():
    def __init__(self):
        pass

    def run_heruistic_preprocessing(self):
        hp = HeuristicPreprocessing()
        hp.main()

    def run_heruistic_postprocessing(self):
        hp = HeuristicPostprocessing()
        hp.main()


    # Env Helpers
    def get_latest_runtime(self, path, *paths) -> str:
        """Returns the name of the latest (most recent) file 
        of the joined path(s)"""
        fullpath = os.path.join(path, *paths)
        list_of_files = glob.glob(fullpath)  # You may use iglob in Python3
        if not list_of_files:                # I prefer using the negation
            return None                      # because it behaves like a shortcut
        latest_file = max(list_of_files, key=os.path.getctime)
        _, filename = os.path.split(latest_file)
        time = filename.split("_")[2]
        return time

    def set_latest_runtime(self, timestamp: str):
        dotenv.set_key(dotenv.find_dotenv(),"latest_timestamp", timestamp)
        print("Timestamp latest runtime set.")

    def produce_dashboard(self, db_path: str):
            app = dashboard.App(db_path)
            app.mainloop()

    def main():
        pass


if __name__ == "__main__":

    SUMO_OUTPUT_PATH: str = "/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/sumo/output/"
    eb = EbusMain()
    timestamp = eb.get_latest_runtime(SUMO_OUTPUT_PATH, "*")
    eb.set_latest_runtime(timestamp)
    eb.produce_dashboard(r"C:\Users\Ralop\Documents\FU Berlin\BeST-eBuS\best-ebus\scenario\eBuS\database\ebus.db")
    pass