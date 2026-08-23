"""
Main entry point for the analysis package.

This module coordinates the individual analysis modules:
    - bus_timing
    - energy_consumption
    - vehicle_soc
    - output_files
"""

from __future__ import annotations

from pathlib import Path

from analysis.output_files import OutputFiles
from analysis.bus_timing import BusTiming
from analysis.energy_consumption import EnergyConsumption
from analysis.vehicle_soc import VehicleSOC
from analysis.ess_pv import ESSPV
from analysis.chargingstation_map import ChargingStationMap
from analysis.sumo_inbuilds import SumoInbuilds

def main(output_dir: str | Path = r"best-ebus\scenario\sumo\output"):
    """Run the complete analysis pipeline."""

    print("Starting analysis...")

    # 0. Load output files
    output_dir = Path(output_dir)
    files = OutputFiles(output_dir)
    # Dictionary of file types and paths
    file_dict = files.get_run_files()

    # Directory to save generated plots to
    plots_dir = output_dir / "plots" / files.timestamp

    # Load other files
    e_bus_directory = output_dir.parent / "electric"
    stops_path = output_dir.parent / "berlin_bus_stops.add.xml"

    # 5. Plot ESS PV Interactions
    esspv = ESSPV(file_dict["ess"], stations_path=e_bus_directory / "e_stations.add.xml")
    esspv.plot_grid_power_by_station(top_n=5, save_path=plots_dir / "grid_power_by_station.svg")
    esspv.plot_pv_vs_charged(save_path=plots_dir / "pv_vs_charged.svg")
    esspv.plot_grid_and_curtailment(save_path=plots_dir / "grid_and_curtailment.svg")
    esspv.plot_ess_soc(save_path=plots_dir / "ess_soc.svg")

    # 6. Create Heatmaps by plotting chargingstations map
    csm_e = ChargingStationMap(stations_path=e_bus_directory / "e_stations.add.xml", chargingstations_path=file_dict["chargingstations"])
    csm_e.plot_energy_map(save_path=plots_dir / "energy_map.svg")
    csm_pv = ChargingStationMap(stations_path=e_bus_directory / "e_stations.add.xml", ess_path=file_dict["ess"])
    csm_pv.plot_pv_generation_map(save_path=plots_dir / "pv_map.svg")
    csm_pv.plot_pv_curtailment_map(save_path=plots_dir / "pv_curtailed_map.svg")

    # 3. Analyse energy consumption
    ec = EnergyConsumption(file_dict["chargingstations"])
    ec.calculate_energy_distribution()
    ec.plot_charging_events(save_path=plots_dir / "charging_events.svg")

    # 1. Run SUMO's own inbuilt analysis/plotting tools
    si = SumoInbuilds()
    # Takes a long time to compute, doesnt really change between runs
    #si.plot_trajectories(file_dict["fcdinfo"], save_path=plots_dir / "all_locations.svg")
    si.compute_stopping_place_usage(file_dict["stopinfo"])
    si.trip_statistics(file_dict["tripinfo"], save_path=plots_dir / "tripinfo_statistics.txt")
    si.plot_battery_energy(file_dict["battery_aggregated"], save_path=plots_dir / "battery_energy.svg")
    si.plot_charging_events_scatter(file_dict["chargingstations"], save_path=plots_dir / "energy_charged_scatter.svg")

    # 2. Analyse bus timing
    bt = BusTiming(file_dict["stopinfo"])
    bt.plot_active_long_stops(save_path=plots_dir / "plot_active_long_stops.svg")
    bt.plot_aggregated_delays(interval=60, save_path=plots_dir / "aggregated_delays.svg")
    bt.plot_delay_per_bus(save_path=plots_dir / "delay_per_bus.svg")

    # 4. Analyse vehicle state of charge
    v_soc = VehicleSOC(file_dict["battery_aggregated"])
    v_soc.plot_cumulative_soc(save_path=plots_dir / "cumulative_soc.svg")
    v_soc.calculate_trip_end_soc()

    print("Analysis completed.")

if __name__ == "__main__":
    main()