__author__ = "Sven Vorgheim"
__license__ = "GPL v2 or later (In accordance to SUMO)"
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
from .coordinate_calculator import CoordinateCalculator

class HeuristicPreprocessing:
    def __init__(
            self,
            routes_file: Path,
            stations_file: Path,
            network_file: Path,
            selected_lines: dict[str, list[str]],
            depots: tuple,
            stations_coordinates_file: Path,
            trips_file: Path,
            termination_points_file: Path,
            deadhead_file: Path,
            preprocessed_routes_file: Path):
        """stations_file is only read; the bus stops with coordinates are written to stations_coordinates_file."""
        self.routes_file = routes_file
        self.stations_file = stations_file
        self.network_file = network_file
        self.selected_lines = selected_lines
        self.depots = depots
        self.stations_coordinates_file = stations_coordinates_file
        self.trips_file = trips_file
        self.termination_points_file = termination_points_file
        self.deadhead_file = deadhead_file
        self.preprocessed_routes_file = preprocessed_routes_file

    def main(self):

        cc = CoordinateCalculator(self.network_file, self.stations_file)
        cc.add_coordinates_to_bus_stops()
        cc.save(self.stations_coordinates_file)

        # needs the coordinates for the trips
        fl = FilterLines(self.routes_file, self.selected_lines, self.stations_coordinates_file, self.trips_file)
        fl.main()

        tp = TerminationPoints(fl.routes_root, self.depots, self.termination_points_file)
        tp.main()

        cl = CutLines(self.stations_file, fl.routes_root)
        trimmed_root = cl.trim_routes()

        # deadheads between the termination points computed above
        dc = DeadheadCalculator(
            self.network_file,
            self.stations_file,
            trimmed_root,
            self.termination_points_file,
            self.depots,
            self.deadhead_file,
            self.preprocessed_routes_file)
        dc.calculate_station_deadheads()
