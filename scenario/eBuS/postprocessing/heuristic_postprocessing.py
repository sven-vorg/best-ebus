# Imports
import json
from lxml import etree
import pandas as pd

class HeuristicPostprocessing:
    def __init__(self):
        pass

    # Helper functions
    def get_routes(self, path) -> set[str]:
        routes = {}
        with open(path, "r") as file:
            data = json.load(file)
        for bus in data["bus_assignments"]:
            routes.update({bus["bus_id"]: bus["trip_sequence"]})
        print(routes)
        return routes

    def join_edges_by_route_id(self, id_list):
        """ Function to join the edges of multiple routes by route id """    
        joined_edges = []
        for trip_id in id_list:
            original_trip_id = self.trip_to_original[trip_id]
            if original_trip_id in self.route_lookup:
                joined_edges.append(self.route_lookup[original_trip_id]["edges"])
        return " ".join(joined_edges)
    
    def join_busStops_by_route_id(self, id_list):
        """ Function append the busStops of multiple routes by route id """    
        joined_stops = []
        for trip_id in id_list:
            original_trip_id = self.trip_to_original[trip_id]
            if original_trip_id in self.route_lookup:
                print(original_trip_id)
                print(self.route_lookup[original_trip_id]["edges"])
                joined_stops.append(self.route_lookup[original_trip_id]["stops"])
        print(joined_stops)
        return joined_stops
    
    def parse_routes(self, xml_file):
        tree = etree.parse(xml_file)
        root = tree.getroot()

        routes = {}

        for route in root.findall("route"):
            route_id = route.get("id")
            routes[route_id] = {
                "color": route.get("color"),
                "edges": route.get("edges"),
                "stops": [
                    {
                        "busStop": stop.get("busStop"),
                        "duration": float(stop.get("duration")) if stop.get("duration") else None,
                        "until": float(stop.get("until")) if stop.get("until") else None,
                        "parking": stop.get("parking") == "true",
                    }
                    for stop in route.findall("stop")
                ],
            }

        return routes

    def adapt_until_values(self, routes: etree.Element):
        for vehicle in routes.findall("vehicle"):
            route = vehicle.find("route")
            if route is None:
                continue

            offset = 0.0
            previous_original_until = None
            previous_adjusted_until = None

            for stop in route.findall("stop"):
                original_until = float(stop.get("until"))

                # New trip detected
                if (
                    previous_original_until is not None
                    and original_until < previous_original_until
                ):
                    offset = previous_adjusted_until

                adjusted_until = original_until + offset
                stop.set("until", str(adjusted_until))

                previous_original_until = original_until
                previous_adjusted_until = adjusted_until

    def main(self):
        INPUT = "./best-ebus/scenario/eBuS/files/solution_cicerostrasse.json"
        DICT = "./best-ebus/scenario/eBuS/files/trips_cicerostrasse.txt"
        ROUTES = "./best-ebus/scenario/eBuS/files/deadhead_routes_cicero_mueller.rou.xml"
        OUTPUT = "./best-ebus/scenario/eBuS/files/optimized_buses.rou.xml"

        # Parse the Input JSON
        with open(INPUT, "r") as f:
            solution = json.load(f)

        # Parse the Dictionary
        df_dict = pd.read_csv(DICT, sep=";")
        self.trip_to_original = df_dict.set_index("TRIP_ID")["ORIGINAL_TRIP_ID"].to_dict()
        self.trip_to_depart = df_dict.set_index("TRIP_ID")["START_TIMESTAMP"].to_dict()

        self.route_lookup = self.parse_routes(ROUTES)


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
                type="Ebusco2.2electric12m",
                depart=str(self.trip_to_depart[bus["trip_sequence"][0]]),
                color="1,0,0",
            )

            route = etree.SubElement(
                vehicle,
                "route",
                edges=self.join_edges_by_route_id(bus["trip_sequence"]),
            )

            # Add all stops from every trip in the sequence
            for trip_id in bus["trip_sequence"]:
                for stop in self.route_lookup[self.trip_to_original[trip_id]]["stops"]:
                    etree.SubElement(
                        route,
                        "stop",
                        busStop=stop["busStop"],
                        duration=str(stop["duration"]),
                        until=str(stop["until"]),
                        parking=str(stop["parking"]).lower(),  # "true"/"false"
                    )

        self.adapt_until_values(routes)

        tree = etree.ElementTree(routes)
        tree.write(
            OUTPUT,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
        )

        print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    hp = HeuristicPostprocessing()
    hp.main()

