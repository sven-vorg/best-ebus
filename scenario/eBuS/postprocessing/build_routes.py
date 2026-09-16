import json
import pandas as pd
from pathlib import Path
from lxml import etree

class BuildRoutes:
    def __init__(self, solution_path: Path, station_id_map_path: Path, trips_path: Path, routes_path: Path, deadhead_timing_path: Path, output_path: Path):
        self.solution_dict = self.parse_solution(solution_path)
        self.station_id_dict = self.parse_station_id_map(station_id_map_path)
        self.trips_df = pd.read_csv(trips_path, sep=";")
        self.original_routes = self.parse_routes(routes_path)
        self.deadhead_timings = pd.read_csv(deadhead_timing_path, sep=";")
        self.output_path = output_path

    def main(self):
        new_routes = {}

        for bus in self.solution_dict["bus_assignments"]:
            route_id = f"bus_{bus["bus_id"]}"
            trip_edges = []
            trip_stops = []
            previous_original_trip_id = None
            for trip in bus["trip_sequence"]:
                original_trip_id = self.trips_df.loc[self.trips_df["TRIP_ID"] == trip, "ORIGINAL_TRIP_ID"].iloc[0]

                if previous_original_trip_id is not None:
                    trip_edges.append(self.build_deadheads(
                        self.original_routes[previous_original_trip_id]["stops"][-1],
                        self.original_routes[original_trip_id]["stops"][0]
                    ))

                trip_edges.append(self.original_routes[original_trip_id]["edges"])

                trip_stops.extend(self.build_stops(trip, original_trip_id, bus["bus_id"]))

                previous_original_trip_id = original_trip_id


            deadheads = self.build_depot_deadheads(bus, trip_stops[0], trip_stops[-1])
            trip_edges.insert(0, deadheads[0])
            trip_edges.append(deadheads[1])
            trip_stops.insert(0, deadheads[2])
            trip_stops.append(deadheads[3])

            self.remove_duplicate_edges(trip_edges)
            self.remove_duplicate_stops(trip_stops)


            trip_edges_string = " ".join(trip_edges)
            new_routes[route_id] = {
                "edges": trip_edges_string,
                "stops": trip_stops
            }
        self.build_xml_routes(new_routes, self.output_path)

    def build_deadheads(self, last_stop, first_stop):
        return self.original_routes[f"{last_stop['busStop']}_{first_stop['busStop']}"]["edges"]

    def remove_duplicate_edges(self, edges):
        all_edges = [edge for group in edges for edge in group.split()]
        deduplicated_edges = [edge for i, edge in enumerate(all_edges) if i == 0 or edge != all_edges[i - 1]]
        edges[:] = deduplicated_edges

    def remove_duplicate_stops(self, stops):
        if not stops:
            return

        deduplicated_stops = [stops[0]]
        for stop in stops[1:]:
            previous_stop = deduplicated_stops[-1]
            if stop["busStop"] != previous_stop["busStop"]:
                deduplicated_stops.append(stop)
                continue

            if "station_id" in stop:
                if float(previous_stop["until"]) > float(stop["until"]):
                    stop["until"] = previous_stop["until"]
                deduplicated_stops[-1] = stop
            elif "station_id" in previous_stop:
                if float(stop["until"]) > float(previous_stop["until"]):
                    previous_stop["until"] = stop["until"]
            elif float(stop["until"]) > float(previous_stop["until"]):
                deduplicated_stops[-1] = stop

        stops[:] = deduplicated_stops
    
    def build_depot_deadheads(self, bus, first_stop, last_stop):
        start_depot = self.station_id_dict[str(bus["start_depot"])]
        end_depot = self.station_id_dict[str(bus["end_depot"])]
        start_depot_edges = self.original_routes[f"{start_depot}_{first_stop['busStop']}"]["edges"]
        end_depot_edges = self.original_routes[f"{last_stop['busStop']}_{end_depot}"]["edges"]
        departure = {
            "busStop": start_depot, 
            "until": f"{float(first_stop['until'])-self.deadhead_timings.loc[(self.deadhead_timings['FromStopID'] == start_depot) & (self.deadhead_timings['ToStopID'] == first_stop['busStop']), 'RunTime'].iloc[0]}"}
        arrival = {
            "busStop": end_depot,
            "until": f"{float(last_stop['until'])+self.deadhead_timings.loc[(self.deadhead_timings['FromStopID'] == last_stop['busStop']) & (self.deadhead_timings['ToStopID'] == end_depot), 'RunTime'].iloc[0]}"
        }
        return start_depot_edges, end_depot_edges, departure, arrival

    def build_stops(self, trip, original_trip_id, route_id):

        trip_departure_time = int(self.trips_df.loc[self.trips_df["TRIP_ID"] == trip, "START_TIMESTAMP"].iloc[0])
        trip_arrival_time = int(self.trips_df.loc[self.trips_df["TRIP_ID"] == trip, "END_TIMESTAMP"].iloc[0])
        
        stops = [dict(stop) for stop in self.original_routes[original_trip_id]["stops"]]
        for stop in stops:
            stop["until"] = str(float(stop["until"]) + trip_departure_time)
            stop["tripId"] = str(trip)
        charging_event = next(
            (
                event for event in self.solution_dict["charging_events"]
                if event["bus_id"] == route_id
                and (
                    event["start_time"]*60 == trip_arrival_time
                    or event["end_time"]*60 == trip_departure_time # may be to imprecise to find every match
                )
            ),
            None
        )
        if charging_event is not None:
            charging_stop = {
                "busStop": str(self.station_id_dict.get(str(charging_event["station_id"]))),
                "until": str(int(charging_event["end_time"]*60)),
                "station_id": f"{charging_event["station_id"]}",
                "tripId": str(trip)
            }
            if charging_event["start_time"]*60 == trip_arrival_time:
                stops.append(charging_stop)
            elif charging_event["end_time"]*60 == trip_departure_time:
                stops.insert(0, charging_stop)
        print(stops)
        return stops

    def build_xml_routes(self, new_routes, output_path):
        root = etree.Element("routes")
        for route_id, route_data in new_routes.items():
            route_element = etree.SubElement(root, "route", id=f"{route_id}_route", edges=route_data["edges"])
            for stop in route_data["stops"]:
                stop_element = etree.SubElement(route_element, "stop", **stop)
        tree = etree.ElementTree(root)
        tree.write(output_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
        
    @staticmethod
    def parse_solution(solution_path):
        with open(solution_path, "r") as f:
            solution_dict = json.load(f)
        return solution_dict

    @staticmethod
    def parse_station_id_map(station_id_map_path):
        with open(station_id_map_path, "r") as f:
            station_id_map = json.load(f)
            station_id_dict = station_id_map["stops"]
        return station_id_dict
    
    @staticmethod
    def parse_routes(routes_path):
        tree = etree.parse(routes_path)
        root = tree.getroot()

        routes_dict = {}
        for route in root.findall("route"):
            route_id = route.get("id")
            routes_dict[route_id] = {
                "edges": route.get("edges"),
                "stops": [stop.attrib for stop in route.findall("stop")]
            }
        return routes_dict
    
if __name__ == "__main__":
    solution_path = Path(r"best-ebus\scenario\eBuS\files\postprocessing_input\solution.json")
    station_id_map_path = Path(r"best-ebus\scenario\eBuS\files\postprocessing_input\station_id_mapping.txt")
    trips_path = Path(r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\eBuS\files\postprocessing_input\trips_vbb.txt")
    routes_path = Path(r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\eBuS\files\postprocessing_input\e_preprocessed_routes.rou.xml")
    deadhead_timing_path = Path(r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\eBuS\files\postprocessing_input\deadhead_times.txt")
    output_path = Path(r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\sumo\electric\e_routes.rou.xml")
    build_routes = BuildRoutes(solution_path, station_id_map_path, trips_path, routes_path, deadhead_timing_path, output_path)
    build_routes.main()