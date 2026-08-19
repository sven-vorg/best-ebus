from __future__ import annotations
__author__ = "Sven Vorgheim"
__license__ = "GPL v2 or later (In accoardance to SUMO)"
__maintainer__ = "Sven Vorgheim"
__email__ = "sven.vorgheim@fu-berlin.de"
__status__ = "Prototype"
__date__ = "02.07.2026"

import subprocess
from pathlib import Path

import logging

from analysis.output_files import OutputFiles

from pv_estimation.pvgis_api_v6 import PVGISApiCall
from energy_storage_system.charging_station import ChargingStation
from energy_storage_system.energy_storage_system import EnergyStorageSystem
from postprocessing.heuristic_postprocessing import HeuristicPostprocessing
from preprocessing.heuristic_preprocessing import HeuristicPreprocessing
from tools.betterAggregateBattery import aggregate



logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
SCENARIO_ROOT = PROJECT_ROOT.parent

SUMO_DIR = SCENARIO_ROOT / "sumo"
SUMO_OUTPUT_DIR = SUMO_DIR / "output"
EBUS_DIR = SCENARIO_ROOT / "eBuS"
FILES_DIR = EBUS_DIR / "files"
PV_CSV_PATH = EBUS_DIR / "pv_estimation/data/solar_power_v6_scaled.csv"

class EBusMain:
    def __init__(self) -> None:
        """Create an eBuS controller."""

    def run_heuristic_preprocessing(self):
        routes_file: Path = SUMO_DIR / "berlin_bus.rou.xml"
        stations_file: Path = SUMO_DIR / "berlin_bus_stops.add.xml"
        network_file: Path = SUMO_DIR / "berlin.net.xml"

        selected_lines_file: Path = FILES_DIR / "preprocessing_input/depot_line_type.csv"
        combined_routes: Path = FILES_DIR / "cicero_mueller_routes.rou.xml"
        trimmed_routes: Path = FILES_DIR / "cicero_mueller_routes_trimmed.rou.xml"
        termination_points: Path = FILES_DIR / "preprocessing_input/termination_points.txt"

        depots: tuple[str,str] = ("cicerostrasse", "muellerstrasse")
        
        output_dir: Path = FILES_DIR / "postprocessing_input"

        HeuristicPreprocessing(
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
        logger.info("Heuristic Preprocessing completed")

    def run_heuristic_postprocessing(self):
        network_file: Path = (PROJECT_ROOT / "../sumo/berlin.net.xml").resolve()
        stations_file: Path = (PROJECT_ROOT / "../sumo/berlin_bus_stops.add.xml").resolve()
        routes_file: Path = (FILES_DIR / "cicero_mueller_routes.rou.xml").resolve()
        area_file: Path = (FILES_DIR / "postprocessing_input/pv_area_estimation.csv").resolve()
        deadhead_file: Path = (FILES_DIR / "postprocessing_input/deadhead_times.txt").resolve()
        station_id_path: Path = (FILES_DIR / "postprocessing_input/station_id_mapping.txt").resolve()

        output_dir: Path = (PROJECT_ROOT / "../sumo/electric").resolve()

        solution_file = (PROJECT_ROOT / "../eBuS/files/postprocessing_input/solution.json").resolve()

        trip_file = (PROJECT_ROOT / "../eBuS/files/postprocessing_input/trips_vbb.txt").resolve()

        soc_percentage: int = 100

        merged_routes: Path = (PROJECT_ROOT / "../eBuS/files/merged_routes.rou.xml").resolve()
        merged_routes_output: Path = (
            PROJECT_ROOT / "../sumo/electric/e_routes.rou.xml"
        ).resolve()
        vehicles_output: Path = (
            PROJECT_ROOT / "../sumo/electric/e_vehicles.rou.xml"
        ).resolve()

        HeuristicPostprocessing(
            network_file,
            stations_file,
            routes_file,
            output_dir,
            area_file,
            solution_file,
            trip_file,
            deadhead_file,
            soc_percentage,
            merged_routes,
            merged_routes_output,
            vehicles_output,
            station_id_path
        ).main()
        logger.info("Heuristic Postprocessing completed")

    def main(self):
        pass

    def run_aggreate_battery(self):
        """
        Aggregate the battery data from the latest SUMO battery output
        and write the result back as XML.
        """
        files = OutputFiles(SUMO_OUTPUT_DIR)
        battery_file = files.get_file("battery")
        output_file = files.output_dir / battery_file.name.replace(
            "_battery.xml", "_battery_aggregated.xml"
        )
        interval = 60  # seconds

        aggregate(battery_file, output_file, interval)
        logger.info(f"Aggregated battery data written to {output_file}")

    def run_energy_storage_system(self):
        """
        Build the energy storage system profile from the latest SUMO
        chargingstations output and write the result back as XML.
        """
        files = OutputFiles(SUMO_OUTPUT_DIR)
        chargingstations_file = files.get_file("chargingstations")
        output_file = files.output_dir / chargingstations_file.name.replace(
            "_chargingstations.xml", "_ess.xml"
        )

        EnergyStorageSystem(
            charging_stations=ChargingStation.from_xml(chargingstations_file),
            ess_factor=2.0,  # each station's ESS = ess_factor * that station's total PV yield (Wh)
            # ess_capacity=500000,  # or set a static capacity (Wh) for every station instead
            pv_csv_path=PV_CSV_PATH,
            output_path=output_file,
            start_soc=0.5,  # fraction (0.0-1.0) of each station's own ESS capacity
        ).main()
        logger.info(f"ESS output written to {output_file}")

    def run_pvgis_api_call(self):
        """
        Execute the PVGIS v6 API call
        May result in a high number of calls at first run,
        or after creating new charging stations. 
        May be rate limited server side.
        """
        cs_path = (SUMO_DIR / "electric/e_stations.add.xml")
        pv_out = (EBUS_DIR /"pv_estimation/data")
        pvgis = PVGISApiCall(stations_path=cs_path,output_path=pv_out)
        pvgis.main()


    def run_simulation(self):
        """
        Execute the SUMO simulation using the electric bus configuration.
        """
        config_path = (PROJECT_ROOT / "../sumo/e_berlin-bus.sumocfg").resolve()
        result = subprocess.run([
            "sumo",
            "-c", f"{str(config_path)}"
        ])
        logger.info("SUMO finished.")
        logger.info(result.returncode)

if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent

    SUMO_OUTPUT_PATH: Path = Path(HERE.parent / "sumo/output/")
    eb = EBusMain()
    #eb.run_heuristic_preprocessing()
    #eb.run_heuristic_postprocessing()
    #eb.run_simulation()
    #eb.run_aggreate_battery()
    #eb.run_pvgis_api_call()
    eb.run_energy_storage_system()

    