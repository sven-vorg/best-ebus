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

        for chargingStation in cs_root.findall("id"):
            id = chargingStation.get(id)
            if id.partition("_")[2] not in combined_stations:
                cs_root.remove(chargingStation)


        # Write XML
        tree = etree.ElementTree(cs_root)
        tree.write(
            "./best-ebus/scenario/eBuS/files/charging_stations_heuristic.add.xml",
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )

if __name__ == "__main__":
    hp = HeuristicPostprocessing()
    hp.charging_stations_from_solution()
