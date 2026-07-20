#!/usr/bin/env python
__author__ = "Sven Vorgheim"
__license__ = "GPL v2 or later (In accoardance to SUMO)"
__maintainer__ = "Sven Vorgheim"
__email__ = "sven.vorgheim@fu-berlin.de"
__status__ = "Prototype"
__date__ = "02.07.2026"

# Imports
from pathlib import Path

from .filter_lines import FilterLines
from .cut_lines import CutLines
from .deadhead_calculator import DeadheadCalculator
from .termination_points import TerminationPoints

class HeuristicPreprocessing:
    def __init__(
            self, 
            routes_file: Path, 
            stations_file: Path,
            network_file: Path,
            selected_lines_file: Path, 
            combined_routes: Path, 
            trimmed_routes: Path, 
            termination_points: Path,
            depots: tuple, 
            output_dir: Path):
        self.routes_file = routes_file
        self.stations_file = stations_file
        self.network_file = network_file
        self.selected_lines_file = selected_lines_file
        self.combined_routes = combined_routes
        self.trimmed_routes = trimmed_routes
        self.termination_points = termination_points
        self.depots = depots
        self.output_dir = output_dir

    def main(self):

        fl = FilterLines(self.routes_file, self.selected_lines_file, self.output_dir)
        fl.main()

        tp = TerminationPoints(self.combined_routes, self.depots, self.output_dir)
        tp.main()

        cl = CutLines(self.stations_file, self.combined_routes, self.trimmed_routes)
        cl.trim_routes()

        dc = DeadheadCalculator(
            self.network_file, 
            self.stations_file, 
            self.trimmed_routes, 
            self.termination_points, 
            self.depots, 
            self.output_dir)
        dc.calculate_edge_deadheads()

if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent

    routes_file: Path = (HERE / "../../sumo/berlin_bus.rou.xml").resolve()
    stations_file: Path = (HERE / "../../sumo/berlin_bus_stops.add.xml")
    network_file: Path = (HERE / "../../sumo/berlin.net.xml").resolve()

    selected_lines_file: Path = (HERE / "../files/depot_line_type.csv").resolve()
    combined_routes: Path = (HERE / "../files/cicero_mueller_routes.rou.xml").resolve()
    trimmed_routes: Path = HERE / "../files/cicero_mueller_routes_trimmed.rou.xml"
    termination_points: Path = (HERE / "../files/termination_points.txt").resolve()

    depots: tuple = ("cicerostrasse", "muellerstrasse")
    
    output_dir: Path = (HERE / "../files").resolve()

    hp = HeuristicPreprocessing(
        routes_file, 
        stations_file,
        network_file,
        selected_lines_file, 
        combined_routes, 
        trimmed_routes,
        termination_points,
        depots,
        output_dir)
    hp.main()