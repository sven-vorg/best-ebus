# Imports
import logging
from datetime import date
from pathlib import Path

from pv_estimation.pvgis_api_v6 import PVGISApiCall

from .station_id_matching import StationIdMatching
from .charging_stations import ChargingStations
from .build_vehicles import BuildVehicles
from .build_routes import BuildRoutes

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class HeuristicPostprocessing:
    def __init__(
            self,
            net: Path,
            station_root: Path,
            route_root: Path,
            output_path: Path,
            area_path: Path,
            input_path: Path,
            input_dict: Path,
            deadhead_path:Path,
            soc_percentage: int,
            merged_routes: Path,
            merged_routes_output: Path,
            vehicles_output: Path,
            station_id_path: Path,
            chargingstation_power: int = 150000,
            total_power_factor: float = 2,
            offset: int | None = None,
            despawn_offset: int = 0,
            allow_depot_charging: bool = True,
            depot_total_power_factor: float = 2,
            inactive_list: list | None = None,
            pv_start_date: date | None = None,
            pv_data_path: Path | None = None,
            energy_parameters: dict | None = None,
            ):
        """pv_start_date and pv_data_path enable the PV estimation, the stations then get
        the PV data of <pv_data_path>/<pv_start_date>_solar_power_v6_scaled.csv.
        energy_parameters are passed on to ChargingStations, e.g. ses_factor, ses_drawPower or pv_factor."""
        self.net = net
        self.station_root = station_root
        self.route_root = route_root
        self.output_path = output_path
        self.area_path = area_path
        self.input_path = input_path
        self.input_dict = input_dict
        self.deadhead_path = deadhead_path
        self.merged_routes = merged_routes
        self.merged_routes_output = merged_routes_output
        self.vehicles_output = vehicles_output
        self.soc_percentage = soc_percentage
        self.station_id_path = station_id_path
        self.chargingstation_power = chargingstation_power
        self.total_power_factor = total_power_factor
        self.offset = offset
        self.despawn_offset = despawn_offset
        self.allow_depot_charging = allow_depot_charging
        self.depot_total_power_factor = depot_total_power_factor
        self.inactive_list = inactive_list
        self.pv_start_date = pv_start_date
        self.pv_data_path = pv_data_path
        self.energy_parameters = energy_parameters or {}

    def main(self):
        # Stations designated as charging opportunitys
        stations = StationIdMatching(
            station_root=self.station_root,
            area_path=self.area_path,
            solution_path=self.input_path,
            station_id_path=self.station_id_path,
            inactive_list=self.inactive_list,
        ).main()

        # PV for stations
        pv_csv_path = None
        if self.pv_start_date is not None and self.pv_data_path is not None:
            PVGISApiCall(stations=stations, output_path=self.pv_data_path, start_date=self.pv_start_date).main()
            pv_csv_path = Path(self.pv_data_path) / f"{self.pv_start_date}_solar_power_v6_scaled.csv"
            logger.info("PV estimation completed.")

        # Create e_stations.add.xml
        cs = ChargingStations(
            stations=stations,
            output_path=self.output_path,
            power=self.chargingstation_power,
            total_power_factor=self.total_power_factor,
            allow_depot_charging=self.allow_depot_charging,
            depot_total_power_factor=self.depot_total_power_factor,
            pv_csv_path=pv_csv_path,
            **self.energy_parameters,
        )
        cs.main()
        logger.info("Step 1/2 completed: Charging station generation.")

        bv = BuildVehicles(
            solution_path=self.input_path,
            vehicles_output=self.vehicles_output,
            soc_percentage=self.soc_percentage,
            tripp_dict=self.input_dict,
            deadhead_path=self.deadhead_path,
            offset=self.offset,
        )
        bv.main()

        br = BuildRoutes(
            solution_path=self.input_path,
            station_id_map_path=self.station_id_path,
            trips_path=self.input_dict,
            routes_path=self.merged_routes,
            deadhead_timing_path=self.deadhead_path,
            output_path=self.merged_routes_output,
            despawn_offset=self.despawn_offset,
        )
        br.main()
        
if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent
    
    net = Path(HERE / "../../sumo/berlin.net.xml").resolve()
    station_root = Path(HERE / "../../sumo/berlin_bus_stops.add.xml").resolve()
    route_root = Path(HERE / "../files/postprocessing_input/e_preprocessed_routes.rou.xml").resolve()
    output_path = Path(HERE / "../../sumo/electric/").resolve()
    area_path = Path(HERE / "../files/postprocessing_input/pv_area_estimation.csv").resolve()
    station_id_path = Path(HERE / "../files/postprocessing_input/station_id_mapping.txt").resolve()

    input_path = Path(HERE / "../files/postprocessing_input/solution.json").resolve()
    input_dict = Path(HERE / "../files/postprocessing_input/trips_vbb.txt").resolve()
    deadhead_path = Path(HERE / "../files/postprocessing_input/deadhead_times.txt").resolve()
    merged_routes = Path(HERE / "../files/postprocessing_input/e_preprocessed_routes.rou.xml").resolve()
    merged_routes_output = Path(HERE / "../../sumo/electric/e_routes.rou.xml").resolve()
    vehicles_output = Path(HERE / "../../sumo/electric/e_vehicles.rou.xml").resolve()

    hp = HeuristicPostprocessing(
        net=net,
        station_root=station_root,
        route_root=route_root,
        output_path=output_path,
        area_path=area_path,
        input_path=input_path,
        input_dict=input_dict,
        deadhead_path=deadhead_path,
        merged_routes=merged_routes,
        merged_routes_output=merged_routes_output,
        vehicles_output=vehicles_output,
        soc_percentage=50,
        station_id_path= station_id_path
    )
    hp.main()

