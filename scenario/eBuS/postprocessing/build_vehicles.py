from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any
from lxml import etree

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class BuildVehicles:
    def __init__(
        self,
        solution_path: Path,
        vehicles_output: Path,
        soc_percentage: int
    ):
        self.SOLUTION_PATH = solution_path
        self.VEHICLES_OUTPUT = vehicles_output
        self.SOC_PERCENTAGE = soc_percentage

    def main(self):
        with self.SOLUTION_PATH.open("r") as f:
            solution = json.load(f)

        nsmap = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
        vehicles_root = etree.Element("routes", nsmap=nsmap)

        for bus in solution["bus_assignments"]:
            self._build_vehicles(bus, vehicles_root)

        self._write_xml(vehicles_root, self.VEHICLES_OUTPUT)
        logger.info("Wrote %s", self.VEHICLES_OUTPUT)

    def _build_vehicles(self, bus, vehicles_root):
        vehicle = etree.SubElement(
            vehicles_root,
            "vehicle",
            id=str(bus['bus_id']),
            type=self._determine_type(bus["bus_type_name"], bus["bus_id"]),
            route=f"{bus["bus_id"]}_route",
            depart="0",
            color="1,0,0",
        )
        etree.SubElement(
            vehicle,
            "param",
            key="device.battery.chargeLevel",
            value=self._determine_soc(bus["bus_type_name"], bus["bus_id"]),
        )

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