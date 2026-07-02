# Imports
import json
from lxml import etree

class HeuristicPostprocessing:
    def __init__(self):
        pass

    # Helper functions
    def get_station_decisions(self, path) -> set[str]:
        charging_locations = set()
        with open(path, "r") as file:
            data = json.load(file)
        for station_decision in data["station_decisions"]:
            charging_locations.add(station_decision["station_id"])
        return charging_locations
    
    def charging_stations_from_solution(self):
        # Parse JSON File
        solution_cicerostrasse = "./best-ebus/scenario/eBuS/files/solution_cicerostrasse.json"

        solution_muellerstrasse = "./best-ebus/scenario/eBuS/files/solution_muellerstrasse.json"

        # Parse xml file
        tree = etree.parse("./best-ebus/scenario/eBuS/files/charging_stations.add.xml")
        cs_root = tree.getroot()

        combined_stations = (
            self.get_station_decisions(solution_muellerstrasse) 
            | self.get_station_decisions(solution_cicerostrasse)
        )

        cs_root = etree.Element(
            "additional",
            nsmap={
                "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            },
        )

        cs_root.set(
            "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation",
            "http://sumo.dlr.de/xsd/additional_file.xsd",
        )

        for chargingStation in cs_root.findall("id"):
            id = chargingStation.get(id)
            if id.partition("_")[2] not in combined_stations:
                cs_root.remove(chargingStation)


        # Write XML
        tree = etree.ElementTree(cs_root)
        tree.write(
            "../files/charging_stations_heuristic.add.xml",
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )

if __name__ == "__main__":
    hp = HeuristicPostprocessing()
    hp.charging_stations_from_solution()
