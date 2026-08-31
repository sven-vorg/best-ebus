"""
Registry of analysis methods available to the dashboard.

Each entry wires one plotting/analysis call from the `analysis` package to a
run's output files (as produced by `EBusMain.order_output`, see
`analysis/output_files.py`) and to the shared `sumo/electric` network files.

To add a new method to the dashboard: write a small wrapper function with
the signature `(files: dict[str, Path], sumo_dir: Path, plots_dir: Path) -> None`
and append an `AnalysisMethod` entry to `METHODS` below. No other dashboard
code needs to change - it will show up in the method list automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from analysis.bus_timing import BusTiming
from analysis.chargingstation_map import ChargingStationMap
from analysis.energy_consumption import EnergyConsumption
from analysis.ess_pv import ESSPV
from analysis.infrastructure_map import InfrastructureMap
from analysis.sumo_inbuilds import SumoInbuilds
from analysis.trip_info import TripInfo
from analysis.vehicle_soc import VehicleSOC


@dataclass(frozen=True)
class AnalysisMethod:
    name: str
    category: str
    func: Callable[[dict, Path, Path], None]
    description: str = ""
    default_selected: bool = True


def _stations_path(sumo_dir: Path) -> Path:
    return sumo_dir / "electric" / "e_stations.add.xml"


def _routes_path(sumo_dir: Path) -> Path:
    return sumo_dir / "electric" / "e_routes.rou.xml"


def _busstops_path(sumo_dir: Path) -> Path:
    return sumo_dir / "berlin_bus_stops.add.xml"


# --- SUMO inbuilt tools ------------------------------------------------

def _trip_statistics(files, sumo_dir, plots_dir):
    SumoInbuilds().trip_statistics(files["tripinfo"], plots_dir / "tripinfo_statistics.txt")


def _stopping_place_usage(files, sumo_dir, plots_dir):
    SumoInbuilds().compute_stopping_place_usage(files["stopinfo"])


def _battery_energy_sumo(files, sumo_dir, plots_dir):
    SumoInbuilds().plot_battery_energy(files["battery_aggregated"], plots_dir / "battery_energy.pdf")


def _charging_events_scatter(files, sumo_dir, plots_dir):
    SumoInbuilds().plot_charging_events_scatter(files["chargingstations"], plots_dir / "energy_charged_scatter.pdf")


def _trajectories(files, sumo_dir, plots_dir):
    SumoInbuilds().plot_trajectories(files["fcdinfo"], plots_dir / "all_locations.pdf")


# --- Bus timing ----------------------------------------------------------

def _active_long_stops(files, sumo_dir, plots_dir):
    BusTiming(files["stopinfo"]).plot_active_long_stops(save_path=plots_dir / "plot_active_long_stops.pdf")


def _aggregated_delays(files, sumo_dir, plots_dir):
    BusTiming(files["stopinfo"]).plot_aggregated_delays(interval=60, save_path=plots_dir / "aggregated_delays.pdf")


def _delay_per_bus(files, sumo_dir, plots_dir):
    BusTiming(files["stopinfo"]).plot_delay_per_bus(save_path=plots_dir / "delay_per_bus.pdf")


# --- Energy consumption ----------------------------------------------------

def _energy_distribution(files, sumo_dir, plots_dir):
    EnergyConsumption(files["chargingstations"]).calculate_energy_distribution()


def _charging_events(files, sumo_dir, plots_dir):
    EnergyConsumption(files["chargingstations"]).plot_charging_events(save_path=plots_dir / "charging_events.pdf")


# --- Trip info -----------------------------------------------------------

def _route_length_vs_energy(files, sumo_dir, plots_dir):
    TripInfo(files["tripinfo"]).plot_route_length_vs_energy(
        save_path=plots_dir / "route_length_vs_energy.pdf"
    )


def _energy_efficiency(files, sumo_dir, plots_dir):
    TripInfo(files["tripinfo"]).calculate_energy_efficiency()


# --- Vehicle state of charge -------------------------------------------

def _cumulative_soc(files, sumo_dir, plots_dir):
    VehicleSOC(files["battery_aggregated"]).plot_cumulative_soc(save_path=plots_dir / "cumulative_soc.pdf")


def _trip_end_soc(files, sumo_dir, plots_dir):
    VehicleSOC(files["battery_aggregated"]).calculate_trip_end_soc()


def _soc_over_time(files, sumo_dir, plots_dir):
    VehicleSOC(files["battery_aggregated"]).plot_soc_over_time(
        files["tripinfo"], save_path=plots_dir / "soc_over_time.pdf"
    )


# --- ESS / PV --------------------------------------------------------------

def _ess_soc(files, sumo_dir, plots_dir):
    ESSPV(files["ess"], stations_path=_stations_path(sumo_dir)).plot_ess_soc(
        save_path=plots_dir / "ess_soc.pdf"
    )


def _pv_vs_charged(files, sumo_dir, plots_dir):
    ESSPV(files["ess"], stations_path=_stations_path(sumo_dir)).plot_pv_vs_charged(
        save_path=plots_dir / "pv_vs_charged.pdf"
    )


def _grid_and_curtailment(files, sumo_dir, plots_dir):
    ESSPV(files["ess"], stations_path=_stations_path(sumo_dir)).plot_grid_and_curtailment(
        save_path=plots_dir / "grid_and_curtailment.pdf"
    )


def _grid_power_by_station(files, sumo_dir, plots_dir):
    ESSPV(files["ess"], stations_path=_stations_path(sumo_dir)).plot_grid_power_by_station(
        top_n=5, save_path=plots_dir / "grid_power_by_station.pdf"
    )


def _pv_power(files, sumo_dir, plots_dir):
    ESSPV(files["ess"], stations_path=_stations_path(sumo_dir)).plot_pv_power(
        save_path=plots_dir / "pv_power.pdf"
    )


# --- Charging station maps --------------------------------------------

def _energy_map(files, sumo_dir, plots_dir):
    ChargingStationMap(
        stations_path=_stations_path(sumo_dir),
        chargingstations_path=files["chargingstations"],
    ).plot_energy_map(save_path=plots_dir / "energy_map.pdf")


def _pv_generation_map(files, sumo_dir, plots_dir):
    ChargingStationMap(
        stations_path=_stations_path(sumo_dir),
        ess_path=files["ess"],
    ).plot_pv_generation_map(save_path=plots_dir / "pv_map.pdf")


def _pv_curtailment_map(files, sumo_dir, plots_dir):
    ChargingStationMap(
        stations_path=_stations_path(sumo_dir),
        ess_path=files["ess"],
    ).plot_pv_curtailment_map(save_path=plots_dir / "pv_curtailed_map.pdf")


# --- Infrastructure map -----------------------------------------------

def _infrastructure_map(files, sumo_dir, plots_dir):
    InfrastructureMap(
        busstops_path=_busstops_path(sumo_dir),
        stations_path=_stations_path(sumo_dir),
        routes_path=_routes_path(sumo_dir),
    ).plot_infrastructure_map(save_path=plots_dir / "infrastructure_map.pdf")


METHODS: list[AnalysisMethod] = [
    AnalysisMethod(
        "Trip statistics", "SUMO inbuilt tools", _trip_statistics,
        "Write aggregated trip statistics to a text file.",
    ),
    AnalysisMethod(
        "Stopping place usage", "SUMO inbuilt tools", _stopping_place_usage,
        "Print stopping-place usage statistics.",
    ),
    AnalysisMethod(
        "Battery energy", "SUMO inbuilt tools", _battery_energy_sumo,
        "Plot energy consumed per bus over time.",
    ),
    AnalysisMethod(
        "Charging events scatter", "SUMO inbuilt tools", _charging_events_scatter,
        "Scatter plot of charging events (energy vs. start time).",
    ),
    AnalysisMethod(
        "Vehicle trajectories", "SUMO inbuilt tools", _trajectories,
        "Scatter plot of all recorded vehicle positions. Slow; rarely changes between runs.",
        default_selected=False,
    ),
    AnalysisMethod(
        "Active long stops", "Bus timing", _active_long_stops,
        "Number of buses in a stop longer than 20s, per interval.",
    ),
    AnalysisMethod(
        "Aggregated delays", "Bus timing", _aggregated_delays,
        "Mean bus delay per 60-second interval.",
    ),
    AnalysisMethod(
        "Delay per bus", "Bus timing", _delay_per_bus,
        "Delay over simulation time, one line per bus.",
    ),
    AnalysisMethod(
        "Energy distribution", "Energy consumption", _energy_distribution,
        "Print total/depot/opportunity energy charged.",
    ),
    AnalysisMethod(
        "Charging events", "Energy consumption", _charging_events,
        "Plot charging events over time by charging type.",
    ),
    AnalysisMethod(
        "Route length vs energy", "Trip info", _route_length_vs_energy,
        "Scatter plot of route length vs. total energy consumed per bus, colored by vehicle type.",
    ),
    AnalysisMethod(
        "Energy efficiency", "Trip info", _energy_efficiency,
        "Print average energy efficiency (kWh/km) per vehicle type.",
    ),
    AnalysisMethod(
        "Cumulative SOC", "Vehicle state of charge", _cumulative_soc,
        "Cumulative battery energy of all buses over the day.",
    ),
    AnalysisMethod(
        "Trip-end SOC", "Vehicle state of charge", _trip_end_soc,
        "Print SoC statistics at trip end and at last depot entry.",
    ),
    AnalysisMethod(
        "SOC over time", "Vehicle state of charge", _soc_over_time,
        "State of charge over simulation time, one line per bus, colored by vehicle type.",
    ),
    AnalysisMethod(
        "ESS state of charge", "ESS / PV", _ess_soc,
        "Battery SoC per charging station over the day.",
    ),
    AnalysisMethod(
        "PV vs charged", "ESS / PV", _pv_vs_charged,
        "PV generated vs. energy charged, per station.",
    ),
    AnalysisMethod(
        "Grid & curtailment", "ESS / PV", _grid_and_curtailment,
        "System-wide grid energy drawn and curtailed PV.",
    ),
    AnalysisMethod(
        "Grid power by station", "ESS / PV", _grid_power_by_station,
        "Grid power drawn (kW) over time, top 5 stations.",
    ),
    AnalysisMethod(
        "PV power by station", "ESS / PV", _pv_power,
        "PV power generated (kW) over time, per station, excluding depots.",
    ),
    AnalysisMethod(
        "Energy map", "Charging station maps", _energy_map,
        "Map sized by total energy charged per station.",
    ),
    AnalysisMethod(
        "PV generation map", "Charging station maps", _pv_generation_map,
        "Map sized by total PV energy generated per station.",
    ),
    AnalysisMethod(
        "PV curtailment map", "Charging station maps", _pv_curtailment_map,
        "Map sized by total PV energy curtailed per station.",
    ),
    AnalysisMethod(
        "Infrastructure map", "Infrastructure", _infrastructure_map,
        "Map of bus stops, charging stations and depots. Rarely changes between runs.",
        default_selected=False,
    ),
]
