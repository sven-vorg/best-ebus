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
from .coordinate_calculator import CoordinateCalculator

class HeuristicPreprocessing:
    def __init__(
            self,
            routes_file: Path,
            stations_file: Path,
            network_file: Path,
            selected_lines_file: Path,
            termination_points: Path,
            depots: tuple,
            output_dir: Path):
        self.routes_file = routes_file
        self.stations_file = stations_file
        self.network_file = network_file
        self.selected_lines_file = selected_lines_file
        self.termination_points = termination_points
        self.depots = depots
        self.output_dir = output_dir

    def main(self):

        cc = CoordinateCalculator(self.network_file, self.stations_file)
        cc.add_coordinates_to_bus_stops()
        cc.save()

        fl = FilterLines(self.routes_file, self.selected_lines_file, self.stations_file, self.output_dir)
        fl.main()

        tp = TerminationPoints(fl.routes_root, self.depots, self.output_dir)
        tp.main()

        cl = CutLines(self.stations_file, fl.routes_root)
        trimmed_root = cl.trim_routes()

        dc = DeadheadCalculator(
            self.network_file,
            self.stations_file,
            trimmed_root,
            self.termination_points,
            self.depots,
            self.output_dir)
        dc.calculate_station_deadheads()

if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent

    routes_file: Path = (HERE / "../../sumo/berlin_bus.rou.xml").resolve()
    stations_file: Path = (HERE / "../../sumo/berlin_bus_stops.add.xml")
    network_file: Path = (HERE / "../../sumo/berlin.net.xml").resolve()
    selected_lines_file: Path = (HERE / "../files/preprocessing_input/depot_line_type.csv").resolve()

    termination_points: Path = (HERE / "../files/preprocessing_input/termination_points.txt").resolve()

    depots: tuple = ("cicerostrasse", "muellerstrasse")

    output_dir: Path = (HERE / "../postprocessing_input/files").resolve()

    hp = HeuristicPreprocessing(
        routes_file,
        stations_file,
        network_file,
        selected_lines_file,
        termination_points,
        depots,
        output_dir)
    hp.main()