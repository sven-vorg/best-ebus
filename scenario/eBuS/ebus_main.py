#!/usr/bin/env python
__author__ = "Sven Vorgheim"
__license__ = "GPL v2 or later (In accoardance to SUMO)"
__maintainer__ = "Sven Vorgheim"
__email__ = "sven.vorgheim@fu-berlin.de"
__status__ = "Prototype"
__date__ = "02.07.2026"

import os
import glob
import sys
import dotenv
import subprocess
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
        routes_file: Path = (PROJECT_ROOT / "../sumo/berlin_bus.rou.xml").resolve()
        stations_file: Path = (PROJECT_ROOT / "../sumo/berlin_bus_stops.add.xml")
        network_file: Path = (PROJECT_ROOT / "../sumo/berlin.net.xml").resolve()

        selected_lines_file: Path = (PROJECT_ROOT / "../eBuS/files/depot_line_type.csv").resolve()
        combined_routes: Path = (PROJECT_ROOT / "../eBuS/files/cicero_mueller_routes.rou.xml").resolve()
        trimmed_routes: Path = (PROJECT_ROOT / "../eBuS/files/cicero_mueller_routes_trimmed.rou.xml").resolve()
        termination_points: Path = (PROJECT_ROOT / "../eBuS/files/termination_points.txt").resolve()

        depots: tuple = ("cicerostrasse", "muellerstrasse")
        
        output_dir: Path = (PROJECT_ROOT / "../eBuS/files").resolve()
        hp = HeuristicPreprocessing(
            routes_file,
            stations_file,
            network_file,
            selected_lines_file,
            combined_routes,
            trimmed_routes,
            termination_points,
            depots,
            output_dir,
        ).main()

    def run_heruistic_postprocessing(self):
        network_file: Path = (PROJECT_ROOT / "../sumo/berlin.net.xml").resolve()
        stations_file: Path = (PROJECT_ROOT / "../sumo/berlin_bus_stops.add.xml").resolve()
        routes_file: Path = (PROJECT_ROOT / "../eBuS/files/cicero_mueller_routes.rou.xml").resolve()

        output_dir: Path = (PROJECT_ROOT / "../sumo/electric").resolve()

        solution_files: list[Path] = [
            (PROJECT_ROOT / "../eBuS/files/solution_cicerostrasse.json").resolve(),
            (PROJECT_ROOT / "../eBuS/files/solution_muellerstrasse.json").resolve(),
        ]

        trip_files: list[Path] = [
            (PROJECT_ROOT / "../eBuS/files/trips_cicerostrasse.txt").resolve(),
            (PROJECT_ROOT / "../eBuS/files/trips_muellerstrasse.txt").resolve(),
        ]

        merged_routes: Path = (PROJECT_ROOT / "../eBuS/files/merged_routes.rou.xml").resolve()
        merged_routes_output: Path = (
            PROJECT_ROOT / "../sumo/electric/e_routes.rou.xml"
        ).resolve()
        vehicles_output: Path = (
            PROJECT_ROOT / "../sumo/electric/e_vehicles.rou.xml"
        ).resolve()

        hp = HeuristicPostprocessing(
            network_file,
            stations_file,
            routes_file,
            output_dir,
            solution_files,
            trip_files,
            merged_routes,
            merged_routes_output,
            vehicles_output,
        ).main()

    def update_database(self):
        DBeBuS()._update_db()


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
            app = dashboard.Dashboard(db_path)

    def main(self):
        pass

    def run_simulation(self):
        config_path = (PROJECT_ROOT / "../sumo/e_berlin-bus.sumocfg").resolve()
        result = subprocess.run([
            "sumo",
            "-c", f"{str(config_path)}"
        ])
        print("SUMO finished.")
        print(result.returncode)

if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent

    SUMO_OUTPUT_PATH: Path = Path(HERE.parent / "sumo/output/")

    eb = EbusMain()
    eb.run_heruistic_preprocessing()
    eb.run_heruistic_postprocessing()
    eb.run_simulation()
    timestamp = eb.get_latest_runtime(SUMO_OUTPUT_PATH, "*")
    if timestamp is not None:
        print(f"Latest runtime: {timestamp}")
        eb.set_latest_runtime(timestamp)
    eb.update_database()
    

    #eb.produce_dashboard(db_path=Path(HERE /"database/ebus.db"))
    pass