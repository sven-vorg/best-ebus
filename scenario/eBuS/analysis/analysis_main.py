"""
Main entry point for the analysis package.

This module coordinates the individual analysis modules:
    - bus_timing
    - energy_consumption
    - vehicle_soc
    - output_files
"""

from pathlib import Path

from output_files import OutputFiles
from bus_timing import BusTiming
from energy_consumption import EnergyConsumption
from vehicle_soc import VehicleSOC
from ess_pv import ESSPV
from chargingstation_map import ChargingStationMap
from sumo_inbuilds import SumoInbuilds

def main():
    """Run the complete analysis pipeline."""

    print("Starting analysis...")

    # 0. Load output files
    output_dir = r"best-ebus\scenario\sumo\output"
    files = OutputFiles(output_dir)
    # Dictionary of file types and paths
    file_dict = files.get_run_files()

    # Directory to save generated plots to
    plots_dir = Path(output_dir) / "plots" / files.timestamp

    # Load other files
    e_bus_directory = Path(r"best-ebus\scenario\sumo\electric")
    stops_path = r"best-ebus\scenario\sumo\berlin_bus_stops.add.xml"




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

    # 5. Plot ESS PV Interactions
    esspv = ESSPV(file_dict["ess"])
    esspv.plot_pv_vs_charged(save_path=plots_dir / "pv_vs_charged.svg")
    esspv.plot_grid_and_curtailment(save_path=plots_dir / "grid_and_curtailment.svg")
    esspv.plot_ess_soc(save_path=plots_dir / "ess_soc.svg")

    print("Analysis completed.")

if __name__ == "__main__":
    main()