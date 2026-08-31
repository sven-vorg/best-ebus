"""
Main entry point for the analysis package.

This module coordinates the individual analysis modules:
    - bus_timing
    - energy_consumption
    - vehicle_soc
    - output_files
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # never pop up interactive plot windows when run from the CLI

from analysis.output_files import OutputFiles
from analysis.bus_timing import BusTiming
from analysis.energy_consumption import EnergyConsumption
from analysis.vehicle_soc import VehicleSOC
from analysis.trip_info import TripInfo
from analysis.ess_pv import ESSPV
from analysis.chargingstation_map import ChargingStationMap
from analysis.infrastructure_map import InfrastructureMap
from analysis.sumo_inbuilds import SumoInbuilds


class _Tee:
    """File-like object that mirrors writes to multiple streams."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, text):
        for stream in self._streams:
            stream.write(text)

    def flush(self):
        for stream in self._streams:
            stream.flush()


@contextlib.contextmanager
def _logged_section(name, log_file):
    """
    Run a block of code with stdout mirrored into `log_file`, preceded
    by a '# name_of_origin' heading so prints from different steps stay
    distinguishable in the saved log.
    """

    log_file.write(f"# {name}\n")
    original_stdout = sys.stdout
    sys.stdout = _Tee(original_stdout, log_file)
    try:
        yield
    finally:
        sys.stdout = original_stdout
        log_file.write("\n")


def main(
    output_dir: str | Path = r"best-ebus\scenario\sumo\output",
    sumo_dir: str | Path = r"best-ebus\scenario\sumo",
):
    """
    Run the complete analysis pipeline.

    output_dir: the run_<timestamp> folder (created by
        EBusMain.order_output) containing that run's SUMO/ESS output files.
    sumo_dir: the base sumo directory, used to locate the electric
        network files and bus stops that are shared across runs.
    """

    print("Starting analysis...")

    # 0. Load output files
    output_dir = Path(output_dir)
    sumo_dir = Path(sumo_dir)
    files = OutputFiles(output_dir)
    # Dictionary of file types and paths
    file_dict = files.get_run_files()

    # Directory to save generated plots to
    plots_dir = output_dir / "plots"

    # Load other files
    e_bus_directory = sumo_dir / "electric"
    stops_path = sumo_dir / "berlin_bus_stops.add.xml"

    log_path = plots_dir / "analysis_log.txt"
    plots_dir.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w", encoding="utf-8") as log_file:

        # 5. Plot ESS PV Interactions
        with _logged_section("Plot ESS PV Interactions", log_file):
            esspv = ESSPV(file_dict["ess"], stations_path=e_bus_directory / "e_stations.add.xml")
            esspv.plot_grid_power_by_station(top_n=5, save_path=plots_dir / "grid_power_by_station.pdf")
            esspv.plot_pv_vs_charged(save_path=plots_dir / "pv_vs_charged.pdf")
            esspv.plot_grid_and_curtailment(save_path=plots_dir / "grid_and_curtailment.pdf")
            esspv.plot_ess_soc(save_path=plots_dir / "ess_soc.pdf")

        # 6. Create Heatmaps by plotting chargingstations map
        with _logged_section("Create Heatmaps by plotting chargingstations map", log_file):
            csm_e = ChargingStationMap(stations_path=e_bus_directory / "e_stations.add.xml", chargingstations_path=file_dict["chargingstations"])
            csm_e.plot_energy_map(save_path=plots_dir / "energy_map.pdf")
            csm_pv = ChargingStationMap(stations_path=e_bus_directory / "e_stations.add.xml", ess_path=file_dict["ess"])
            csm_pv.plot_pv_generation_map(save_path=plots_dir / "pv_map.pdf")
            csm_pv.plot_pv_curtailment_map(save_path=plots_dir / "pv_curtailed_map.pdf")

        # 3. Analyse energy consumption
        with _logged_section("Analyse energy consumption", log_file):
            ec = EnergyConsumption(file_dict["chargingstations"])
            ec.calculate_energy_distribution()
            ec.plot_charging_events(save_path=plots_dir / "charging_events.pdf")

        # 1. Run SUMO's own inbuilt analysis/plotting tools
        with _logged_section("Run SUMO's own inbuilt analysis/plotting tools", log_file):
            si = SumoInbuilds()
            # Takes a long time to compute, doesnt really change between runs
            #si.plot_trajectories(file_dict["fcdinfo"], save_path=plots_dir / "all_locations.pdf")
            si.compute_stopping_place_usage(file_dict["stopinfo"])
            si.trip_statistics(file_dict["tripinfo"], save_path=plots_dir / "tripinfo_statistics.txt")
            si.plot_battery_energy(file_dict["battery_aggregated"], save_path=plots_dir / "battery_energy.pdf")
            si.plot_charging_events_scatter(file_dict["chargingstations"], save_path=plots_dir / "energy_charged_scatter.pdf")

        # 2. Analyse bus timing
        with _logged_section("Analyse bus timing", log_file):
            bt = BusTiming(file_dict["stopinfo"])
            bt.plot_active_long_stops(save_path=plots_dir / "plot_active_long_stops.pdf")
            bt.plot_aggregated_delays(interval=60, save_path=plots_dir / "aggregated_delays.pdf")
            bt.plot_delay_per_bus(save_path=plots_dir / "delay_per_bus.pdf")

        # 4. Analyse vehicle state of charge
        with _logged_section("Analyse vehicle state of charge", log_file):
            v_soc = VehicleSOC(file_dict["battery_aggregated"])
            v_soc.plot_cumulative_soc(save_path=plots_dir / "cumulative_soc.pdf")
            v_soc.calculate_trip_end_soc()
            v_soc.plot_soc_over_time(file_dict["tripinfo"], save_path=plots_dir / "soc_over_time.pdf")

        # 8. Analyse trip info (route length vs. energy consumed)
        with _logged_section("Analyse trip info", log_file):
            ti = TripInfo(file_dict["tripinfo"])
            ti.plot_route_length_vs_energy(save_path=plots_dir / "route_length_vs_energy.pdf")
            ti.calculate_energy_efficiency()

        # 7. Plot infrastructure map (bus stops, charging stations, depots)
        # rarely changing once plotted
        #im = InfrastructureMap(
        #    busstops_path=stops_path,
        #    stations_path=e_bus_directory / "e_stations.add.xml",
        #    routes_path=e_bus_directory / "e_routes.rou.xml",
        #)
        #im.plot_infrastructure_map(save_path=plots_dir / "infrastructure_map.pdf")

    print("Analysis completed.")

if __name__ == "__main__":
    main()