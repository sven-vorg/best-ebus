# Imports
import logging
from pathlib import Path

from .charging_stations import ChargingStations
from .route_concatenation import RouteConcatenation

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class HeuristicPostprocessing:
    def __init__(
            self,
            net: Path,
            station_root: Path,
            route_root: Path,
            output_path: Path,
            input_path: list[Path],
            input_dict: list[Path],
            merged_routes: Path,
            merged_routes_output: Path,
            vehicles_output: Path,
            ):
        self.net = net
        self.station_root = station_root
        self.route_root = route_root
        self.output_path = output_path
        self.input_path = input_path
        self.input_dict = input_dict
        self.merged_routes = merged_routes
        self.merged_routes_output = merged_routes_output
        self.vehicles_output = vehicles_output

    def main(self):
        # Create e_stations.add.xml containing stations designated as charging opportunitys
        cs = ChargingStations(
            net=self.net,
            station_root=self.station_root,
            route_root=self.route_root,
            output_path=self.output_path
        )
        cs.main()

        # Work in Progress
        # pv for stations

        for i, depot_file in enumerate(self.input_path):
            logger.info(
                "Running RouteConcatenation for Depot: '%s'",
                self.input_dict[i]
            )
            depot = Path(depot_file).stem.removeprefix("solution_")
            rc = RouteConcatenation(
                input_path=self.input_path[i],
                input_dict=self.input_dict[i],
                merged_routes=self.merged_routes,
                merged_routes_output=self.merged_routes_output,
                vehicles_output=self.vehicles_output,
                depot_id=depot,
                append = (i > 0) # Setting append true for all iterations after 0
            )
            rc.main()

if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent
    
    net = Path(HERE / "../../sumo/berlin.net.xml").resolve()
    station_root = Path(HERE / "../../sumo/berlin_bus_stops.add.xml").resolve()
    route_root = Path(HERE / "../files/cicero_mueller_routes.rou.xml").resolve()
    output_path = Path(HERE / "../../sumo/electric/").resolve()

    input_path = [Path(HERE / "../files/solution_cicerostrasse.json").resolve(), Path(HERE / "../files/solution_muellerstrasse.json").resolve()]
    input_dict = [Path(HERE / "../files/trips_cicerostrasse.txt").resolve(),Path(HERE / "../files/trips_muellerstrasse.txt").resolve()]
    merged_routes = Path(HERE / "../files/merged_routes.rou.xml").resolve()
    merged_routes_output = Path(HERE / "../../sumo/electric/e_routes.rou.xml").resolve()
    vehicles_output = Path(HERE / "../../sumo/electric/e_vehicles.rou.xml").resolve()

    hp = HeuristicPostprocessing(
        net=net,
        station_root=station_root,
        route_root=route_root,
        output_path=output_path,
        input_path=input_path,
        input_dict=input_dict,
        merged_routes=merged_routes,
        merged_routes_output=merged_routes_output,
        vehicles_output=vehicles_output
    )
    hp.main()

