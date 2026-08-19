from __future__ import annotations
import json
import os
import logging
from pathlib import Path
from typing import Any
import subprocess
import pandas as pd
from lxml import etree

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Length of a simulation day in seconds, used to loop the last deadhead
# back to the start of the (next) simulated day.
DAY_LENGTH = 86400

class BuildVehicles:
    def __init__(
        self,
        solution_path: Path,
        vehicles_output: Path,
        soc_percentage: int,
        tripp_dict: Path,
        deadhead_path: Path,
    ):
        self.SOLUTION_PATH = solution_path
        self.VEHICLES_OUTPUT = vehicles_output
        self.SOC_PERCENTAGE = soc_percentage

        # Set available depots
        self.DEPOTS = {
            1: "bs_cicerostrasse",
            2: "bs_muellerstrasse",
        }

        self._load_trip_dictionary(tripp_dict)
        self._load_deadhead_dictionary(deadhead_path)

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _load_trip_dictionary(self, tripp_dict: Path) -> None:
        """
        Parse trips_vbb.txt into per-trip lookup dicts.

        The file maps every TRIP_ID to its original SUMO trip id, its
        start/end stop, and its scheduled departure/arrival timestamps.
        """
        trip_df = pd.read_csv(tripp_dict, sep=";").set_index("TRIP_ID")
        self.trip_to_end: dict[Any, Any] = trip_df["END_STOP_ID"].to_dict()
        self.trip_to_arrival: dict[Any, Any] = trip_df["END_TIMESTAMP"].to_dict()

    def _load_deadhead_dictionary(self, deadhead_path: Path) -> None:
        self.stations_to_time = {}

        with deadhead_path.open("r", encoding="utf-8") as f:
            next(f)  # skip header

            for line in f:
                from_stop_id, to_stop_id, runtime = line.strip().split(";")
                self.stations_to_time[(from_stop_id, to_stop_id)] = int(runtime)

    def main(self):
        with self.SOLUTION_PATH.open("r") as f:
            solution = json.load(f)

        nsmap = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
        vehicles_root = etree.Element("routes", nsmap=nsmap)

        for bus in solution["bus_assignments"]:
            self._build_vehicles(bus, vehicles_root)

        self.run_sort_routes(vehicles_root)
        self._write_xml(vehicles_root, self.VEHICLES_OUTPUT)
        logger.info("Wrote %s", self.VEHICLES_OUTPUT)


    def _build_vehicles(self, bus, vehicles_root):
        vehicle = etree.SubElement(
            vehicles_root,
            "vehicle",
            id=str(bus['bus_id']),
            type=self._determine_type(bus["bus_type_name"], bus["bus_id"]),
            route=f"{bus["bus_id"]}_route",
            depart=str(self.calculate_departure(bus)),
            color="1,0,0",
        )
        etree.SubElement(
            vehicle,
            "param",
            key="device.battery.chargeLevel",
            value=self._determine_soc(bus["bus_type_name"], bus["bus_id"]),
        )

    def calculate_departure(self, bus) -> int:
        """
        Computes the vehicle's depart time so that its last deadhead of the
        (previous) simulated day loops into the start of the current one:
        last trip_end + deadhead (last stop -> end depot) - one day.
        """
        trip_sequence: list = bus["trip_sequence"]
        end_depot = self.DEPOTS[bus["end_depot"]]

        last_trip_id = trip_sequence[-1]
        last_trip_end_stop = self.trip_to_end[last_trip_id]
        last_trip_end_time = self.trip_to_arrival[last_trip_id]
        deadhead = self.stations_to_time[(last_trip_end_stop, end_depot)]

        overflow = (last_trip_end_time + deadhead) - DAY_LENGTH
        if overflow > 0:
            return int(overflow)
        else:
            return 0

    def run_sort_routes(self, root: etree.Element) -> None:
        """
        SUMO requires vehicles in a route file to appear in ascending
        departure order, so sort the vehicle elements in place by depart.
        """
        root[:] = sorted(root, key=lambda vehicle: int(vehicle.get("depart")))

    def _write_xml(self, root: etree.Element, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        etree.ElementTree(root).write(
            str(path),
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
            )

    # Rewrite these functions at some point to pull information from e_type.add.xml
    def _determine_soc(self, bus_type: str, bus_id: str) -> str:
        """ Determines SoC at sim start """
        if bus_type == "Ebusco_12_525":
            return str(525000/100 * self.SOC_PERCENTAGE)
        elif bus_type == "Solaris_12_300":
            return str(300000/100 * self.SOC_PERCENTAGE)
        elif bus_type == "Solaris_18_528":
            return str(700000/100 * self.SOC_PERCENTAGE)
        else:
            logger.warning(
                "Unknown bus_type_name '%s' for bus %s; defaulting to 525.000 Wh battery capacity", bus_type, bus_id)
            return str(525000 * self.SOC_PERCENTAGE)

    def _determine_type(self, bus_type: str, bus_id: str):
        """ Determines Type of Vehicle """
        if bus_type == "Ebusco_12_525":
            return "Ebusco2.2electric12m"
        elif bus_type == "Solaris_12_300":
            return "SolarsisUrbino12electric"
        elif bus_type == "Solaris_18_528":
            return "SolarsisUrbino18electric"
        else:
            logger.warning(
                "Unknown bus_type_name '%s' for bus %s; defaulting to Ebusco2.2electric12m", bus_type, bus_id)
            return "Ebusco2.2electric12m"