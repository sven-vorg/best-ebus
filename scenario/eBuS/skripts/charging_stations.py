# Imports
from lxml import etree
import pandas as pd

class CharginStations():

    def __init__(self):

        self.STATIONS = "best-ebus/scenario/sumo/berlin_bus_stops.add.xml"
        station_tree = etree.parse(self.STATIONS)
        self.STATION_ROOT = station_tree.getroot()

        self.ROUTES = "best-ebus/scenario/ebus/files/cicero_mueller_routes.rou.xml"
        route_tree = etree.parse(self.ROUTES)
        self.ROUTE_ROOT = route_tree.getroot()

        self.OUTPUT_PATH = "best-ebus/scenario/ebus/files/"

    def txt_for_heuristic(self):
        df = pd.DataFrame(self.get_final_stop_ids())
        df.to_csv(f"{self.OUTPUT_PATH}termination_points.txt", index=False, sep=";")

    def get_final_stop_ids(self):
        # Store unique final stop IDs
        final_stop_ids = set()

        # Collect unique final stop IDs
        for route in self.ROUTE_ROOT.findall("route"):
            stops = route.findall("stop")
            if stops:
                final_stop_ids.add(stops[0].get("busStop"))
                final_stop_ids.add(stops[-1].get("busStop"))
        return final_stop_ids

    def main(self):
        # Store unique final stop IDs
        final_stop_ids = self.get_final_stop_ids()

        # Collect information about those stations
        station_values = []

        for bus_stop in self.STATION_ROOT.findall("busStop"):
            bus_stop_id = bus_stop.get("id")

            if bus_stop_id in final_stop_ids:
                station_values.append({
                    "id": bus_stop_id,
                    "lane": bus_stop.get("lane"),
                    "startPos": bus_stop.get("startPos"),
                    "endPos": bus_stop.get("endPos"),
                    "name": bus_stop.get("name"),
                    "friendlyPos": bus_stop.get("friendlyPos"),
                    "parkingLength": bus_stop.get("parkingLength"),
        })
        
        # Create the root element
        additional = etree.Element("additional")

        # Create one charging station for each station
        for station in station_values:
            etree.SubElement(
                additional,
                "chargingStation",
                id=f"{station['id']}",
                name=f"{station['name']} Charger",
                lane=station["lane"],
                startPos=station["startPos"],
                endPos=station["endPos"],
                power="150000",
                efficiency="0.95",
                chargeInTransit="false",
                friendlyPos="true",
            )

        # Insert charging stations at the beginning of the <additional> element
        additional.insert(
            0,
            etree.Element(
                "chargingStation",
                id="cd_Cicerostrasse_01",
                name="Depot Cicerostraße",
                lane="E1.51_0",
                startPos="0",
                endPos="275.24",
                power="150000",
                efficiency="0.95",
                chargeInTransit="false",
            ),
        )

        additional.insert(
            0,
            etree.Element(
                "chargingStation",
                id="cd_Muellerstrasse_01",
                name="Depot Müllerstraße",
                lane="-E19_0",
                startPos="0",
                endPos="510.64",
                power="150000",
                efficiency="0.95",
                chargeInTransit="false",
            ),
        )

        # Write the XML to a file
        tree = etree.ElementTree(additional)
        tree.write(
            f"{self.OUTPUT_PATH}termination_points.add.xml",
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )

if __name__ == "__main__":
    cs = CharginStations()
    cs.main()