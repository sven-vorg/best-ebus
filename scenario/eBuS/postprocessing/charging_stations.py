"""Skript to create charging stations accoarding busstop ids"""
from lxml import etree
import pandas as pd
import sumolib
from pathlib import Path
import json
import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class ChargingStations():

    def __init__(
            self,
            net: Path,
            station_root: Path,
            route_root: Path,
            output_path: Path,
            area_path: Path,
            solution_path: Path,
            station_id_path: Path,
            power: int = 150000,
            total_power_factor: float = 2
            ):
        self.net = sumolib.net.readNet(net)
        self.STATION_ROOT = etree.parse(station_root).getroot()
        self.ROUTE_ROOT = etree.parse(route_root).getroot()
        self.OUTPUT_PATH = output_path
        self.AREA_LOOKUP = self.area_lookup(pd.read_csv(area_path, sep=";"))
        self.SOLUTION = solution_path
        self.station_id_mapping = self.station_id_lookup(station_id_path)
        self.POWER = power
        self.TOTAL_POWER_FACTOR = total_power_factor

    def station_id_lookup(self, terminationpoints_path: str) -> dict:
        """
        Loads the termination points file and returns a dict mapping
        short station IDs (as strings, e.g. "1", "16") to their long
        canonical IDs (e.g. "agg_10045_25_11089_9_12475_23").
        """
        with open(terminationpoints_path, "r") as file:
            data = json.load(file)
        return data["stops"]

    def area_lookup(self, area_df: pd.DataFrame):
        return area_df.set_index("chargingStation_id")["free_area"].to_dict()

    def charging_stations_from_solution(self):
        charging_locations = set()
        with open(self.SOLUTION, "r") as file:
            data = json.load(file)
            for station_decision in data["station_decisions"]:
                if station_decision["investment_period"] is not None:
                    short_id = str(station_decision["station_id"])
                    long_id = self.station_id_mapping.get(short_id)
                    if long_id is None:
                        raise KeyError(
                            f"station_id '{short_id}' not found in station_id_mapping "
                            f"(loaded from termination points file)"
                        )
                    charging_locations.add(long_id)
        return charging_locations



    def main(self):

        # Store unique final stop IDs
        charging_stop_ids = self.charging_stations_from_solution()
        logger.info("Found %s stops to create charging stations at.", len(charging_stop_ids))

        # Create the root element
        additional = etree.Element(
            "additional",
            nsmap={"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
            )

        for bus_stop in self.STATION_ROOT.findall("busStop"):
            if bus_stop.get("id") in charging_stop_ids:
                param = bus_stop.find("param[@key='coordinates']")
                coordinates = param.get("value") if param is not None else None
                etree.SubElement(
                    additional,
                    "chargingStation",
                    id=f"cs_{bus_stop.get('id')}",
                    name=f"{bus_stop.get('name')}_Charger",
                    lane=bus_stop.get("lane"),
                    startPos=bus_stop.get("startPos"),
                    endPos=bus_stop.get("endPos"),
                    power=str(self.POWER),
                    # BUG 3221225477
                    #totalPower="150000",
                    totalPower=str(self.POWER * self.TOTAL_POWER_FACTOR),
                    efficiency="0.95",
                    chargeInTransit="false",
                    friendlyPos="true",
                    parkingLength=bus_stop.get("parkingLength"),
                    chargeDelay="21",
                    coordinates= str(coordinates),
                    area= str(self.AREA_LOOKUP.get(f"cs_{bus_stop.get('id')}"))
            )
        
        # Insert charging stations at the beginning of the <additional> element
        additional.insert(
            0,
            etree.Element(
                "chargingStation",
                id="cd_cicerostrasse_01",
                name="Depot Cicerostraße",
                lane="E1.51_0",
                startPos="0",
                endPos="300",
                power="150000",
                #totalPower="150000",
                efficiency="0.95",
                chargeInTransit="false",
                coordinates= "13.303440333503405,52.492583731258065",
                area= str(self.AREA_LOOKUP.get("cd_cicerostrasse_01"))
            ),
        )

        additional.insert(
            0,
            etree.Element(
                "chargingStation",
                id="cd_muellerstrasse_01",
                name="Depot Müllerstraße",
                lane="-E19_0",
                startPos="0",
                endPos="530",
                power="150000",
                efficiency="0.95",
                chargeInTransit="false",
                coordinates= "13.33776446744273,52.56058715781662",
                area= str(self.AREA_LOOKUP.get("cd_muellerstrasse_01"))
            ),
        )

        additional.insert(
            0,
            etree.Comment(
                f"Generated using {type(self).__name__} Skript on {str(datetime.datetime.now())}")
                )

        # Write the XML to a file
        tree = etree.ElementTree(additional)
        tree.write(
            f"{self.OUTPUT_PATH}/e_stations.add.xml",
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )

if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent
    net = Path(HERE / "../../sumo/berlin.net.xml").resolve()
    station_root = Path(HERE / "../../sumo/berlin_bus_stops.add.xml").resolve()
    route_root = Path(HERE / "../files/cicero_mueller_routes.rou.xml").resolve()
    output_path = Path(HERE / "../../sumo/electric/").resolve()
    area_path = Path(HERE / "../files/postprocessing_input/pv_area_estimation.csv").resolve()
    solution_path = Path(HERE / "../files/postprocessing_input/solution.json").resolve()
    station_id_path = Path(HERE / "../files/postprocessing_input/station_id_mapping.txt").resolve()
    cs = ChargingStations(net, station_root, route_root, output_path, area_path, solution_path, station_id_path)
    cs.main()