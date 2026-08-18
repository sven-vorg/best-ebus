"""
Main entry point for the analysis package.

This module coordinates the individual analysis modules:
    - bus_timing
    - energy_consumption
    - vehicle_soc
    - output_files
"""

from pathlib import Path

from bus_timing import BusTiming
from energy_consumption import EnergyConsumption
from vehicle_soc import VehicleSOC
from output_files import OutputFiles
from ess_pv import ESSPV

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

    # 2. Analyse bus timing
    bt = BusTiming(file_dict["stopinfo"])
    bt.plot_aggregated_delays(interval=60, save_path=plots_dir / "aggregated_delays.png")
    bt.plot_delay_per_bus(save_path=plots_dir / "delay_per_bus.png")

    # 3. Analyse energy consumption
    ec = EnergyConsumption(file_dict["chargingstations"])
    ec.calculate_energy_distribution()
    ec.plot_charging_events(save_path=plots_dir / "charging_events.png")

    # 4. Analyse vehicle state of charge
    v_soc = VehicleSOC(file_dict["battery_aggregated"])
    v_soc.plot_cumulative_soc(save_path=plots_dir / "cumulative_soc.png")
    v_soc.calculate_trip_end_soc()

    # 5. Plot ESS PV Interactions
    esspv = ESSPV(file_dict["ess"])
    esspv.plot_pv_vs_charged(save_path=plots_dir / "pv_vs_charged.png")
    esspv.plot_grid_and_curtailment(save_path=plots_dir / "grid_and_curtailment.png")
    esspv.plot_ess_soc(save_path=plots_dir / "ess_soc.png")

    print("Analysis completed.")

if __name__ == "__main__":
    main()