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

from preprocessing.filter_lines import FilterLines
from cut_lines import CutLines
from deadhead_calculator import DeadheadCalculator
from termination_points import TerminationPoints

class EbusMain():
    def __init__():
        pass

    def run_heruistic_preprocessing():
        fl = FilterLines()
        fl.main()

        tp = TerminationPoints()
        tp.main()

        # Not used atm, shortens lines to last station, maybe sensitivity analysis
        #cl = CutLines()
        #cl.trim_routes()

        dc = DeadheadCalculator()
        dc.calculate_edge_deadheads()

    def run_heruistic_postprocessing():
        # Create e_stations.add.xml containing stations designated as charging opportunitys
        cs = ChargingStations()
        cs.main()

        # Create the combined routes for all electric buses in the simulation
        rc = RouteConcatenation()
        rc.main()

    def get_latest_runtime(path, *paths) -> str:
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

    def set_latest_runtime(timestamp: str):
        dotenv.set_key(dotenv.find_dotenv(),"latest_timestamp", timestamp)
        print("Timestamp latest runtime set.")

    def main():
        pass


if __name__ == "__main__":

    SUMO_OUTPUT_PATH: str = "/home/sven/Dokumente/Masterarbeit/Repos/best-ebus/scenario/sumo/output/"
    timestamp = EbusMain.get_latest_runtime(SUMO_OUTPUT_PATH, "*")
    EbusMain.set_latest_runtime(timestamp)
    pass