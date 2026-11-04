from __future__ import annotations
__author__ = "Sven Vorgheim"
__license__ = "GPL v2 or later (In accoardance to SUMO)"
__maintainer__ = "Sven Vorgheim"
__email__ = "sven.vorgheim@fu-berlin.de"
__status__ = "Prototype"
__date__ = "02.07.2026"

import argparse
import os
import subprocess
import tomllib
from datetime import date, datetime
from pathlib import Path

import logging

from lxml import etree

from output_processing.order_output import order_output
from paths import (
    AREA_FILE, BUS_ROUTES_FILE, BUS_STOPS_COORDINATES_FILE, BUS_STOPS_FILE, CONFIG_DIR, DEADHEAD_FILE,
    NETWORK_FILE, PREPROCESSED_ROUTES_FILE, ROUTES_OUTPUT_FILE, STATION_ID_FILE, STATIONS_OUTPUT_FILE,
    SUMO_DIR, SUMO_OUTPUT_DIR, TERMINATION_POINTS_FILE, TRIP_FILE, TRIPS_BEST_FILE, TYPE_FILE,
    VEHICLES_OUTPUT_FILE, pv_raw_data_file, pv_raw_power_file, pv_scaled_power_file, solution_file,
)
from postprocessing.build_routes import BuildRoutes
from postprocessing.build_vehicles import BuildVehicles
from postprocessing.charging_stations import ChargingStations
from postprocessing.station_id_matching import Station, StationIdMatching
from preprocessing.heuristic_preprocessing import HeuristicPreprocessing
from pv_estimation.pvgis_api_v6 import PVGISApiCall
from simulation.depot_charging_control import parse_seeds, run_seeds

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SUMOCFG = "e_berlin-bus_p.sumocfg"
# old config names "ebus_config_<scenario>.toml" still give "<scenario>" as scenario name
SCENARIO_CONFIG_PREFIX = "ebus_config_"


class EBusMain:
    def __init__(self, config_path: Path) -> None:
        """Create an eBuS controller for the scenario defined in config_path."""
        with open(config_path, "rb") as f:
            self.config = tomllib.load(f)
        # "configs/summer.toml" -> "summer"
        self.scenario_name: str = config_path.stem.removeprefix(SCENARIO_CONFIG_PREFIX)
        # solution = "winter" -> files/postprocessing_input/winter_solution.json
        self.solution_file: Path = solution_file(self.config["heuristic_postprocessing"]["solution"])
        if not self.solution_file.is_file():
            raise FileNotFoundError(f"Solution file {self.solution_file} of scenario config {config_path.name} not found.")

    def main(self):
        self.run_heuristic_preprocessing()
        stations = self.run_station_matching()
        pv_file = self.run_pv_estimation(stations)
        self.run_charging_stations(stations, pv_file)
        self.run_vehicles_and_routes()
        self.run_update_types()
        self.run_simulation_seeds()
        run_dir = order_output(SUMO_OUTPUT_DIR)
        self.rename_scenario_directory(run_dir)

    def run_heuristic_preprocessing(self):
        depots: tuple[str, ...] = tuple(self.config["heuristic_preprocessing"]["depots"])
        selected_lines: dict[str, list[str]] = self.config["heuristic_preprocessing"]["lines"]

        HeuristicPreprocessing(
            routes_file=BUS_ROUTES_FILE,
            stations_file=BUS_STOPS_FILE,
            network_file=NETWORK_FILE,
            selected_lines=selected_lines,
            depots=depots,
            stations_coordinates_file=BUS_STOPS_COORDINATES_FILE,
            trips_file=TRIPS_BEST_FILE,
            termination_points_file=TERMINATION_POINTS_FILE,
            deadhead_file=DEADHEAD_FILE,
            preprocessed_routes_file=PREPROCESSED_ROUTES_FILE,
        ).main()
        logger.info("Heuristic Preprocessing completed")

    def run_station_matching(self) -> list[Station]:
        """
        Determine the charging stations: the depots and the bus stops selected
        in the solution, minus the inactive stations from the config.
        """
        stations = StationIdMatching(
            # with coordinates for the PV estimation
            station_root=BUS_STOPS_COORDINATES_FILE,
            area_path=AREA_FILE,
            solution_path=self.solution_file,
            station_id_path=STATION_ID_FILE,
            inactive_list=self.config["heuristic_postprocessing"].get("inactive_stations"),
        ).main()
        logger.info("Station matching completed: %s charging stations", len(stations))
        return stations

    def run_pv_estimation(self, stations: list[Station]) -> Path:
        """
        Fetch the PV data of the stations for pv_start_date from PVGIS
        (only for stations not fetched before) and return the scaled PV file.
        """
        pv_start_date: date = self.config["photvoltaic_storage_configuration"]["pv_start_date"]
        scaled_power_file = pv_scaled_power_file(pv_start_date)
        PVGISApiCall(
            stations=stations,
            start_date=pv_start_date,
            raw_data_file=pv_raw_data_file(pv_start_date),
            raw_power_file=pv_raw_power_file(pv_start_date),
            scaled_power_file=scaled_power_file,
        ).main()
        logger.info("PV estimation completed: %s", scaled_power_file)
        return scaled_power_file

    def run_charging_stations(self, stations: list[Station], pv_file: Path):
        """
        Write e_stations.add.xml, including the stationary energy storage and PV
        parameters simulated inside SUMO.
        """
        cfg = self.config["heuristic_postprocessing"]
        ess_cfg = self.config["energy_storage_system"]
        ChargingStations(
            stations=stations,
            output_file=STATIONS_OUTPUT_FILE,
            power=cfg["chargingstation_power"],
            total_power_factor=cfg["total_power_factor"],
            allow_depot_charging=cfg.get("allow_depot_charging", True),
            depot_total_power_factor=cfg.get("depot_total_power_factor", 2.0),
            ses_maximumStorageCapacity=ess_cfg.get("ess_capacity"),  # Wh, takes precedence over ess_factor
            ses_factor=ess_cfg.get("ess_factor"),  # capacity (kWh) = ess_factor * PV peak power (kWp)
            ses_stateOfChargeStartUp=ess_cfg["start_soc"],
            ses_drawTarget=ess_cfg["grid_charge_max_soc"],
            ses_drawPower=ess_cfg["grid_charge_power"] * 1000,  # kW -> W
            pv_csv_path=pv_file,
            pv_factor=ess_cfg["pv_factor"],
        ).main()
        logger.info("Charging stations completed")

    def run_vehicles_and_routes(self):
        """Write e_vehicles.rou.xml and e_routes.rou.xml from the bus assignments of the solution."""
        cfg = self.config["heuristic_postprocessing"]
        BuildVehicles(
            solution_path=self.solution_file,
            vehicles_output=VEHICLES_OUTPUT_FILE,
            soc_percentage=cfg["soc_percentage"],
            tripp_dict=TRIP_FILE,
            deadhead_path=DEADHEAD_FILE,
            offset=cfg.get("offset"),
        ).main()
        BuildRoutes(
            solution_path=self.solution_file,
            station_id_map_path=STATION_ID_FILE,
            trips_path=TRIP_FILE,
            routes_path=PREPROCESSED_ROUTES_FILE,
            deadhead_timing_path=DEADHEAD_FILE,
            output_path=ROUTES_OUTPUT_FILE,
            despawn_offset=cfg.get("despawn_offset"),
        ).main()
        logger.info("Vehicles and routes completed")

    def run_update_types(self):
        """
        Write the "Constant Power Intake" and "Energy Recuperation" values from
        the config into the matching params of every vType in e_type.add.xml.
        """
        constant_power_intake: int = self.config["vehicles"]["constant_power_intake"]
        energy_recuperation: float = self.config["vehicles"]["energy_recuperation"]

        new_values = {
            "constantPowerIntake": constant_power_intake,
            "recuperationEfficiency": energy_recuperation,
        }

        tree = etree.parse(str(TYPE_FILE))
        params = tree.getroot().xpath(
            ".//vType/param[@key='constantPowerIntake' or @key='recuperationEfficiency']"
        )

        for param in params:
            param.set("value", str(new_values[param.get("key")]))

        tree.write(str(TYPE_FILE), encoding="UTF-8", xml_declaration=True)
        logger.info(
            f"Set constantPowerIntake to {constant_power_intake} and "
            f"recuperationEfficiency to {energy_recuperation} in {TYPE_FILE}"
        )

    def get_sumo_version(self):
        result = subprocess.run(["sumo", "--version"], capture_output=True, text=True)
        return result.stdout

    def rename_scenario_directory(self, run_dir: Path) -> Path:
        """
        Rename the output directory "run_<date>" to "<scenario>_run_<date>",
        where <scenario> is derived from the config file (e.g. summer, winter,
        reduced, increased). Returns the new path.
        """
        new_dir = run_dir.with_name(f"{self.scenario_name}_{run_dir.name}")
        if new_dir.exists():
            raise FileExistsError(f"Cannot rename {run_dir}: {new_dir} already exists")
        run_dir.rename(new_dir)
        logger.info("Renamed output directory %s -> %s", run_dir.name, new_dir.name)
        return new_dir


    def run_simulation_seeds(self):
        """
        Execute the SUMO simulation once per seed via libsumo (see simulation.depot_charging_control),
        optionally with the depot charging blocked until every bus has left its depot.
        """
        logger.info("Running %s", self.get_sumo_version())

        sumo_bin = Path(os.environ["SUMO_HOME"]) / "bin" / "sumo.exe"
        cfg = self.config["run_simulation_seeds"]
        config_path = SUMO_DIR / cfg.get("sumocfg", DEFAULT_SUMOCFG)
        logger.info("Using SUMO configuration %s", config_path)
        # space-separated list ("70 67 75") or "start:stop" range ("0:100")
        seeds: list[int] = parse_seeds(cfg["seeds"])
        threads: int = cfg.get("threads", 1)
        block_depot_charging: bool = cfg.get("block_depot_charging_until_departure", False)

        start_time = datetime.now()
        logger.info("Multi-seed simulation started at %s", start_time)

        restored_at = run_seeds(
            sumocfg=config_path,
            seeds=seeds,
            vehicles_file=VEHICLES_OUTPUT_FILE,
            threads=threads,
            block_depot_charging_until_departure=block_depot_charging,
            sumo_binary=str(sumo_bin),
        )

        end_time = datetime.now()
        logger.info("Multi-seed simulation ended at %s", end_time)
        logger.info("Multi-seed simulation runtime: %s", end_time - start_time)
        if block_depot_charging:
            for seed, time in restored_at.items():
                logger.info("Seed %s: depot charging restored at %s s", seed, time)


def resolve_config(name: str) -> Path:
    """Accept a path to a config file, a file name in configs/ or a scenario name, e.g. "winter"."""
    for candidate in (Path(name), CONFIG_DIR / name, CONFIG_DIR / f"{name}.toml"):
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"Scenario config '{name}' not found.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the eBuS pipeline for one or more scenarios, one after another.")
    parser.add_argument(
        "configs", nargs="+",
        help='scenario configs: a path, a file name in configs/ or a scenario name, e.g. "winter summer"',
    )
    args = parser.parse_args()
    # load all scenarios first, so a typo or a missing solution fails before hours of simulation
    scenarios = [EBusMain(resolve_config(name)) for name in args.configs]
    for scenario in scenarios:
        logger.info("Running scenario %s with %s", scenario.scenario_name, scenario.solution_file.name)
        scenario.main()
