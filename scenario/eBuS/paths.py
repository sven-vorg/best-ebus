"""All file and directory paths of the eBuS pipeline in one place.

Every file one step writes and another step reads is defined here, so the steps
receive full file paths and never build file names themselves."""
from datetime import date
from pathlib import Path

EBUS_DIR = Path(__file__).resolve().parent
SCENARIO_ROOT = EBUS_DIR.parent

# eBuS
CONFIG_DIR = EBUS_DIR / "configs"
FILES_DIR = EBUS_DIR / "files"
PREPROCESSING_INPUT_DIR = FILES_DIR / "preprocessing_input"
POSTPROCESSING_INPUT_DIR = FILES_DIR / "postprocessing_input"
PV_DATA_DIR = EBUS_DIR / "pv_estimation/data"

# SUMO scenario
SUMO_DIR = SCENARIO_ROOT / "sumo"
SUMO_OUTPUT_DIR = SUMO_DIR / "output"
ELECTRIC_DIR = SUMO_DIR / "electric"

# Network, bus stops and original bus routes of the scenario (only read, never written)
NETWORK_FILE = SUMO_DIR / "berlin.net.xml"
BUS_STOPS_FILE = SUMO_DIR / "berlin_bus_stops.add.xml"
BUS_ROUTES_FILE = SUMO_DIR / "berlin_bus.rou.xml"

# Written by the preprocessing
# copy of BUS_STOPS_FILE with a "coordinates" param per bus stop (lon,lat), used for the trips and the PV
# estimation; not loaded by SUMO, which loads BUS_STOPS_FILE (loading both would duplicate the bus stops)
BUS_STOPS_COORDINATES_FILE = ELECTRIC_DIR / "e_bus_stops.add.xml"
# trips of the selected lines, input for the optimization
TRIPS_BEST_FILE = POSTPROCESSING_INPUT_DIR / "trips_best.txt"
# first and last stops of the selected lines plus the depots
TERMINATION_POINTS_FILE = POSTPROCESSING_INPUT_DIR / "termination_points.txt"
# run times and routes between all termination points
DEADHEAD_FILE = POSTPROCESSING_INPUT_DIR / "deadhead_times.txt"
PREPROCESSED_ROUTES_FILE = POSTPROCESSING_INPUT_DIR / "e_preprocessed_routes.rou.xml"

# Postprocessing input from outside the pipeline (optimization / manual)
STATION_ID_FILE = POSTPROCESSING_INPUT_DIR / "station_id_mapping.txt"
AREA_FILE = POSTPROCESSING_INPUT_DIR / "pv_area_estimation.csv"
TRIP_FILE = POSTPROCESSING_INPUT_DIR / "trips_vbb.txt"

# SUMO input, written by the postprocessing
STATIONS_OUTPUT_FILE = ELECTRIC_DIR / "e_stations.add.xml"
ROUTES_OUTPUT_FILE = ELECTRIC_DIR / "e_routes.rou.xml"
VEHICLES_OUTPUT_FILE = ELECTRIC_DIR / "e_vehicles.rou.xml"
TYPE_FILE = ELECTRIC_DIR / "e_type.add.xml"


def solution_file(name: str) -> Path:
    """Solution of the optimization, e.g. "winter" -> postprocessing_input/winter_solution.json."""
    return POSTPROCESSING_INPUT_DIR / f"{name}_solution.json"


# PV estimation, one set of files per PV date
def pv_raw_data_file(start_date: date) -> Path:
    """Complete PVGIS answers per station, also tells which stations were already fetched."""
    return PV_DATA_DIR / f"{start_date}_raw_pv_data.csv"


def pv_raw_power_file(start_date: date) -> Path:
    """PV power per station and hour as returned by PVGIS."""
    return PV_DATA_DIR / f"{start_date}_solar_power_v6_raw.csv"


def pv_scaled_power_file(start_date: date) -> Path:
    """PV energy per station and hour [Wh], scaled by the installed peak power; read by the charging stations."""
    return PV_DATA_DIR / f"{start_date}_solar_power_v6_scaled.csv"
