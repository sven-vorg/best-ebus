# AI-generated on 2026-07-21

import csv
import os
import sys

from lxml import etree
from pathlib import Path

# Sumo Tools specific import
if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    sys.path.append(tools)
else:
    raise EnvironmentError("Please declare the environment variable 'SUMO_HOME'")

import sumolib

class SumoConfiguration:
    def __init__(self):
        pass

    def write_sumo_config(
        self,
        filename,
        *,
        input_options,
        output_options=None,
        time_options=None,
        processing_options=None,
        random_options=None,
    ):
        """
        Write a SUMO configuration (.sumocfg) file.

        Parameters
        ----------
        filename : Path
            Output .sumocfg filename.

        input_options : dict
            Dictionary of input options.
            List values are automatically joined with ', '.

        output_options : dict, optional
            Dictionary of output options.

        time_options : dict, optional
            Dictionary of time options.

        processing_options : dict, optional
            Dictionary of processing options.

        random_options : dict, optional
            Dictionary of random number options.
        """

        def add_section(parent, section_name, options):
            if not options:
                return

            section = etree.SubElement(parent, section_name)

            for key, value in options.items():
                if value is None:
                    continue

                if isinstance(value, bool):
                    value = str(value).lower()
                elif isinstance(value, (list, tuple)):
                    value = ", ".join(map(str, value))
                else:
                    value = str(value)

                etree.SubElement(section, key, value=value)

        root = etree.Element(
            "configuration",
            nsmap={"xsi": "http://www.w3.org/2001/XMLSchema-instance"},
        )
        root.set(
            "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation",
            "http://sumo.dlr.de/xsd/sumoConfiguration.xsd",
        )

        add_section(root, "input", input_options)
        add_section(root, "output", output_options)
        add_section(root, "time", time_options)
        add_section(root, "processing", processing_options)
        add_section(root, "random_number", random_options)

        etree.ElementTree(root).write(
            filename,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )

if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent
    config = SumoConfiguration()
    print(Path(HERE.parent/ "sumo/e_berlin-bus.sumocfg"))
    config.write_sumo_config(
        Path(HERE.parent.parent/ "sumo/e_berlin-bus.sumocfg"),
        input_options={
            "net-file": "berlin.net.xml",
            "route-files": [
                "electric/e_routes.rou.xml", 
                "electric/e_vehicles.rou.xml"],
            "additional-files": [
                "berlin_bus_stops.add.xml", 
                "electric/e_type.add.xml",
                "electric/e_depots.add.xml",
                "electric/e_stations.add.xml"],
        },
        output_options={
            "output-prefix": "output/electric_bus_TIME_",
            "log": "console.log",
            "summary-output": "summary.xml",
            "statistic-output": "statistics.xml",
            "battery-output": "battery.parquet",
            "chargingstations-output": "chargingstations.parquet",
            "tripinfo-output": "tripinfo.parquet",
            "tripinfo-output.write-unfinished": "true"
        },
        time_options={
            "begin": 0.0,
            "end": 86400.0,
        },
        processing_options={
            "route-steps": 200,
            "no-internal-links": "false",
            "ignore-junction-blocker": 20,
            "time-to-teleport": -500.0,
            "time-to-teleport.highways": 0,
            "eager-insert": "false"
        },

        random_options={
            "random": "false",
            "seed": "251920"
        },
    )