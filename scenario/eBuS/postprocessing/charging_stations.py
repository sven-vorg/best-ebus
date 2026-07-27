"""Skript to create charging stations accoarding busstop ids"""
from lxml import etree
import pandas as pd
import sumolib
from pathlib import Path
import json
from sumolib.geomhelper import positionAtShapeOffset
import datetime

class ChargingStations():

    def __init__(
            self,
            net: Path,
            station_root: Path,
            route_root: Path,
            output_path: Path,
            area_path: Path
            ):
        self.net = sumolib.net.readNet(net)
        self.STATION_ROOT = etree.parse(station_root).getroot()
        self.ROUTE_ROOT = etree.parse(route_root).getroot()
        self.OUTPUT_PATH = output_path
        self.AREA_LOOKUP = self.area_lookup(pd.read_csv(area_path, sep=";"))

    def area_lookup(self, area_df: pd.DataFrame):
        return area_df.set_index("chargingStation_id")["free_area"].to_dict()

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
                    coordinates= self._get_stop_coordinates(bus_stop),
                    area= str(self.AREA_LOOKUP.get(f"cs_{bus_stop.get('id')}"))
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
                coordinates= "13.303440333503405,52.492583731258065",
                area= str(self.AREA_LOOKUP.get("cd_Cicerostrasse_01"))
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
                coordinates= "13.33776446744273,52.56058715781662",
                area= str(self.AREA_LOOKUP.get("cd_Muellerstrasse_01"))
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
    area_path = Path(HERE / "../files/pv_area_estimation.csv").resolve()
    cs = ChargingStations(net, station_root, route_root, output_path)
    cs.main()