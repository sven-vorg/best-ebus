from __future__ import annotations
__author__ = "Sven Vorgheim"
__license__ = "GPL v2 or later (In accoardance to SUMO)"
__maintainer__ = "Sven Vorgheim"
__email__ = "sven.vorgheim@fu-berlin.de"
__status__ = "Prototype"
__date__ = "02.07.2026"

import os
import subprocess
import sys
import tomllib
from datetime import date, datetime
from pathlib import Path

import logging

from analysis.analysis_main import main as run_full_analysis
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
PV_DATA_DIR = EBUS_DIR / "pv_estimation/data"

CONFIG_PATH = PROJECT_ROOT / "ebus_config.toml"
with open(CONFIG_PATH, "rb") as f:
    CONFIG = tomllib.load(f)

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

        depots: tuple[str, ...] = tuple(CONFIG["heuristic_preprocessing"]["depots"])

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

        cfg = CONFIG["heuristic_postprocessing"]
        soc_percentage: int = cfg["soc_percentage"]

        merged_routes: Path = (PROJECT_ROOT / "../eBuS/files/postprocessing_input/merged_routes.rou.xml").resolve()
        merged_routes_output: Path = (
            PROJECT_ROOT / "../sumo/electric/e_routes.rou.xml"
        ).resolve()
        vehicles_output: Path = (
            PROJECT_ROOT / "../sumo/electric/e_vehicles.rou.xml"
        ).resolve()

        chargingstation_power: int = cfg["chargingstation_power"]

        total_power_factor: float = cfg["total_power_factor"]

        offset: int | None = cfg.get("offset")

        despawn_offset: int = cfg.get("despawn_offset", 0)

        allow_depot_charging: bool = cfg.get("allow_depot_charging", True)

        depot_total_power_factor: float = cfg.get("depot_total_power_factor", 2.0)

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
            station_id_path,
            chargingstation_power=chargingstation_power,
            total_power_factor=total_power_factor,
            offset=offset,
            despawn_offset=despawn_offset,
            allow_depot_charging=allow_depot_charging,
            depot_total_power_factor=depot_total_power_factor,
        ).main()
        logger.info("Heuristic Postprocessing completed")

    def main(self):
        PV_START_DATE: date = CONFIG["main"]["pv_start_date"]
        self.run_heuristic_preprocessing()
        self.run_heuristic_postprocessing()
        if "seeds" in CONFIG.get("run_simulation_seeds", {}):
            self.run_simulation_seeds()
        else:
            self.run_simulation()
        self.run_aggreate_battery()
        self.run_pvgis_api_call(start_date=PV_START_DATE)
        self.run_energy_storage_system(start_date=PV_START_DATE)
        self.run_analysis()

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
        interval = CONFIG["aggregate_battery"]["interval"]

        aggregate(battery_file, output_file, interval)
        logger.info(f"Aggregated battery data written to {output_file}")

    def run_energy_storage_system(self, start_date: date):
        """
        Build the energy storage system profile from the latest SUMO
        chargingstations output and write the result back as XML.
        Uses the PV data fetched for start_date by run_pvgis_api_call.
        """
        files = OutputFiles(SUMO_OUTPUT_DIR)
        chargingstations_file = files.get_file("chargingstations")
        output_file = files.output_dir / chargingstations_file.name.replace(
            "_chargingstations.xml", "_ess.xml"
        )
        pv_csv_path = PV_DATA_DIR / f"{start_date}_solar_power_v6_scaled.csv"

        cfg = CONFIG["energy_storage_system"]
        EnergyStorageSystem(
            charging_stations=ChargingStation.from_xml(chargingstations_file),
            ess_factor=cfg.get("ess_factor"),  # each station's ESS = ess_factor * that station's Peak Power (kWh)
            ess_capacity=cfg.get("ess_capacity"),  # or set a static capacity (Wh) for every station instead
            pv_csv_path=pv_csv_path,
            output_path=output_file,
            start_soc=cfg["start_soc"],  # fraction (0.0-1.0) of each station's own ESS capacity
            pv_factor=cfg["pv_factor"],  # scales the PV power generated by each station
            grid_charge_max_soc=cfg["grid_charge_max_soc"],  # always draw from grid below this fraction of SoC
            grid_charge_power=cfg["grid_charge_power"],  # power (kW) drawn from grid while below grid_charge_max_soc
        ).main()
        logger.info(f"ESS output written to {output_file}")

    def run_pvgis_api_call(self, start_date: date):
        """
        Execute the PVGIS v6 API call for the given start_date.
        Data is fetched from start_date 00:00 to the following day 04:59
        and saved with a "<start_date>_" filename prefix. If a file for
        that date already exists, the API calls are skipped.
        May result in a high number of calls at first run,
        or after creating new charging stations.
        May be rate limited server side.
        """
        cs_path = (SUMO_DIR / "electric/e_stations.add.xml")
        pv_out = (EBUS_DIR /"pv_estimation/data")
        pvgis = PVGISApiCall(stations_path=cs_path, output_path=pv_out, start_date=start_date)
        pvgis.main()

    def run_analysis(self):
        """
        Run the full analysis pipeline over the latest SUMO/ESS output
        and save the generated plots.
        """
        run_full_analysis(output_dir=SUMO_OUTPUT_DIR)
        logger.info("Analysis completed")

    def get_sumo_version(self):
        result = subprocess.run(["sumo", "--version"], capture_output=True, text=True)
        return result.stdout

    def run_simulation(self):
        """
        Execute the SUMO simulation using the electric bus configuration.
        """
        logger.info("Running %s", self.get_sumo_version())

        sumo_bin = Path(os.environ["SUMO_HOME"]) / "bin" / "sumo.exe"
        logger.info("from %s directory.", sumo_bin)
        config_path = (PROJECT_ROOT / "../sumo/e_berlin-bus.sumocfg").resolve()

        start_time = datetime.now()
        logger.info("Simulation started at %s", start_time)

        result = subprocess.run([str(sumo_bin), "-c", str(config_path)])

        end_time = datetime.now()
        logger.info("Simulation ended at %s", end_time)
        logger.info("Simulation runtime: %s", end_time - start_time)

        logger.info("SUMO finished.")
        logger.info(result.returncode)

    def run_simulation_seeds(self):
        """
        Execute the SUMO simulation multiple times with different seeds
        using SUMO's runSeeds.py tool (SUMO_HOME/tools/runSeeds.py).
        """
        logger.info("Running %s", self.get_sumo_version())

        sumo_bin = Path(os.environ["SUMO_HOME"]) / "bin" / "sumo.exe"
        run_seeds_script = Path(os.environ["SUMO_HOME"]) / "tools" / "runSeeds.py"
        logger.info("from %s directory.", sumo_bin)
        config_path = (PROJECT_ROOT / "../sumo/e_berlin-bus.sumocfg").resolve()

        cfg = CONFIG["run_simulation_seeds"]
        # runSeeds.py expects a comma-separated list (or a "start:stop" range);
        # the config stores seeds as a space-separated list, so convert here.
        seeds: str = ",".join(cfg["seeds"].split())
        threads: int = cfg.get("threads", 1)

        start_time = datetime.now()
        logger.info("Multi-seed simulation started at %s", start_time)

        result = subprocess.run([
            sys.executable, str(run_seeds_script),
            "-k", str(config_path),
            "-a", str(sumo_bin),
            "-p", "SEED",
            "--seeds", seeds,
            "--threads", str(threads),
            "--statistics-output", "stats.xml"
        ])

        end_time = datetime.now()
        logger.info("Multi-seed simulation ended at %s", end_time)
        logger.info("Multi-seed simulation runtime: %s", end_time - start_time)

        logger.info("SUMO runSeeds finished.")
        logger.info(result.returncode)

if __name__ == "__main__":
    EBusMain().main()

    