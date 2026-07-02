# Imports
import json
from lxml import etree
import pandas as pd

class RouteConcatenation:
    def join_edges_by_route_id(self, id_list):
        """ Function to join the edges of multiple routes by route id """    
        joined_edges = []
        for trip_id in id_list:
            original_trip_id = self.trip_to_original[trip_id]
            if original_trip_id in self.route_lookup:
                joined_edges.append(self.route_lookup[original_trip_id])
        return " ".join(joined_edges)

    def main(self):
        INPUT = "./best-ebus/scenario/eBuS/files/solution_cicerostrasse.json"
        DICT = "./best-ebus/scenario/eBuS/files/trips_cicerostrasse.txt"
        ROUTES = "./best-ebus/scenario/eBuS/files/deadheads_routes_cicero_mueller.rou.xml"
        OUTPUT = "./best-ebus/scenario/eBuS/files/optimized_buses.rou.xml"

        # Parse the Input JSON
        with open(INPUT, "r") as f:
            solution = json.load(f)

        # Parse the Dictionary
        df_dict = pd.read_csv(DICT, sep=";")
        self.trip_to_original = df_dict.set_index("TRIP_ID")["ORIGINAL_TRIP_ID"].to_dict()
        self.trip_to_depart = df_dict.set_index("TRIP_ID")["START_TIMESTAMP"].to_dict()


        # Parse the rou.xml files
        tree = etree.parse(ROUTES)
        route_root = tree.getroot()
        self.route_lookup = {
            route.get("id"): route.get("edges")
            for route in route_root.findall("route")
        }

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
                type="bus",  # or bus["bus_type_name"] if those types are defined
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
            OUTPUT,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
        )

        print(f"Wrote {OUTPUT}")

if __name__ == "__main__":
    rc = RouteConcatenation()
    rc.main()