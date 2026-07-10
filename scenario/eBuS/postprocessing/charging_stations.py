"""Skript to create charging stations accoarding busstop ids"""
from lxml import etree
import pandas as pd
import sumolib
import json
from sumolib.geomhelper import positionAtShapeOffset
import datetime

class ChargingStations():

    def __init__(self):
        self.net = sumolib.net.readNet("best-ebus/scenario/sumo/berlin.net.xml")
        self.STATION_ROOT = etree.parse("best-ebus/scenario/sumo/berlin_bus_stops.add.xml").getroot()
        self.ROUTE_ROOT = etree.parse("best-ebus/scenario/ebus/files/cicero_mueller_routes.rou.xml").getroot()
        self.OUTPUT_PATH = "best-ebus/scenario/sumo/electric/"

    def charging_stations_from_solution(self):
        # Parse JSON File
        solution_cicerostrasse = "./best-ebus/scenario/eBuS/files/solution_cicerostrasse.json"

        solution_muellerstrasse = "./best-ebus/scenario/eBuS/files/solution_muellerstrasse.json"

        return (
            self.get_station_decisions(solution_muellerstrasse) 
            | self.get_station_decisions(solution_cicerostrasse)
        )

    def get_station_decisions(self, path) -> set[str]:
        charging_locations = set()
        with open(path, "r") as file:
            data = json.load(file)
        for station_decision in data["station_decisions"]:
            charging_locations.add(station_decision["station_id"])
        return charging_locations

    def _get_stop_coordinates(self, stop):
        lane_id = stop.get("lane")
        pos = float(stop.get("pos", 0))

        lane = self.net.getLane(lane_id)
        shape = lane.getShape()

        # position along the lane's shape -> network x,y
        x, y = positionAtShapeOffset(shape, pos)

        # network x,y -> lon/lat (WGS84)
        lon, lat = self.net.convertXY2LonLat(x, y)

        return f"{lon:.6f},{lat:.6f}"

    def _add_depots(self, root):
        pass

    def main(self):

        # Store unique final stop IDs
        charging_stop_ids = self.charging_stations_from_solution()
        print(f"Found {len(charging_stop_ids)} stops to create charging stations at.")

        # Create the root element
        additional = etree.Element(
            "additional",
            nsmap={"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
            )

        for bus_stop in self.STATION_ROOT.findall("busStop"):
            if bus_stop.get("id") in charging_stop_ids:
                etree.SubElement(
                    additional,
                    "chargingStation",
                    id=f"cs_{bus_stop.get('id')}",
                    name=f"{bus_stop.get('name')}_Charger",
                    lane=bus_stop.get("lane"),
                    startPos=bus_stop.get("startPos"),
                    endPos=bus_stop.get("endPos"),
                    power="150000",
                    efficiency="0.95",
                    chargeInTransit="false",
                    friendlyPos="true",
                    parkingLength=bus_stop.get("parkingLength"),
                    energyStorageCap="500",
                    coordinates= self._get_stop_coordinates(bus_stop)
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
                energyStorageCap="50000",
                coordinates= "13.303440333503405,52.492583731258065"
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
                energyStorageCap="50000",
                coordinates= "13.33776446744273,52.56058715781662"
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
            f"{self.OUTPUT_PATH}e_stations.add.xml",
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )

if __name__ == "__main__":
    cs = ChargingStations()
    cs.main()