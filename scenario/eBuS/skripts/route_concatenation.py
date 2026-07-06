# Imports
import json
from lxml import etree
import pandas as pd

class RouteConcatenation:

    def __init__(self):
        self.INPUT = "./best-ebus/scenario/eBuS/files/solution_cicerostrasse.json"
        # Parse the Dictionary
        DICT = "./best-ebus/scenario/eBuS/files/trips_cicerostrasse.txt"
        df_dict = pd.read_csv(DICT, sep=";")
        self.trip_to_original = df_dict.set_index("TRIP_ID")["ORIGINAL_TRIP_ID"].to_dict()
        self.trip_to_start = df_dict.set_index("TRIP_ID")["START_STOP_ID"].to_dict()
        self.trip_to_end = df_dict.set_index("TRIP_ID")["END_STOP_ID"].to_dict()
        self.trip_to_depart = df_dict.set_index("TRIP_ID")["START_TIMESTAMP"].to_dict()

        self.ROUTES = "./best-ebus/scenario/eBuS/files/merged_deadheads_routes.rou.xml"

        # Parse the rou.xml files
        tree = etree.parse(self.ROUTES)
        route_root = tree.getroot()
        self.route_lookup = {
            route.get("id"): route.get("edges")
            for route in route_root.findall("route")
        }
        self.OUTPUT = "./best-ebus/scenario/eBuS/files/optimized_buses.rou.xml"

    def main(self):
        # Parse the Input JSON
        with open(self.INPUT, "r") as f:
            solution = json.load(f)

        # Root element of the new route file
        routes = etree.Element(
            "routes",
            nsmap={"xsi": "http://www.w3.org/2001/XMLSchema-instance"},
        )

        # Vehicle type
        etree.SubElement(
            routes,
            "vType",
            id="bus",
            vClass="bus",
        )

        for bus in solution["bus_assignments"]:
            vehicle = etree.SubElement(
                routes,
                "vehicle",
                id=f"cicero_{bus['bus_id']}",
                type="bus",
                depart=str(self.trip_to_depart[bus["trip_sequence"][0]]),
                color="1,0,0",
            )
            etree.SubElement(
                vehicle,
                "route",
                edges=self.join_edges_by_route_id(bus["trip_sequence"]),
            )

        tree = etree.ElementTree(routes)
        tree.write(
            self.OUTPUT,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
        )

        print(f"Wrote {self.OUTPUT}")

    def join_edges_by_route_id(self, id_list):
        """ Function to join the edges of multiple routes by route id """
        depart_station = 1
        joined_edges = []
        for trip_id in id_list:
            joined_edges.append(self.route_lookup[f"{depart_station}_{self.trip_to_start[trip_id]}"])
            original_trip_id = self.trip_to_original[trip_id]
            joined_edges.append(self.route_lookup[original_trip_id])
            depart_station = self.trip_to_end[trip_id]
        joined_edges.append(self.route_lookup[f"{depart_station}_1"])
        result = self.remove_duplicates(" ".join(joined_edges))
        return result

    def remove_duplicates(self, s):
        words = s.split()
        result = []

        for word in words:
            if not result or result[-1] != word:
                result.append(word)
        return(" ".join(result))

    def order_optimized_routes(self):
        tree = etree.parse("best-ebus/scenario/eBuS/files/optimized_buses.rou.xml")
        root = tree.getroot()

        vehicles = root.findall("vehicle")
        for v in vehicles:
            root.remove(v)

        vehicles.sort(key=lambda v: float(v.get("depart")))

        for v in vehicles:
            root.append(v)

        tree.write(
            "best-ebus/scenario/sumo/electric/routes_sorted.rou.xml",
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8"
        )

        print("Wrote sorted route file")

if __name__ == "__main__":
    rc = RouteConcatenation()
    rc.order_optimized_routes()
    rc.main()