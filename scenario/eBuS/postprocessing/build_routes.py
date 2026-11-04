import json
import logging
import pandas as pd
from pathlib import Path
from lxml import etree

logger = logging.getLogger(__name__)

SIMULATION_RUNTIME = 104399
# Tolerance [s] when comparing the charging times of the solution (float minutes) with stop times (s)
TIME_TOLERANCE = 1.0

class BuildRoutes:
    def __init__(
            self, 
            solution_path: Path, 
            station_id_map_path: Path, 
            trips_path: Path, 
            routes_path: Path, 
            deadhead_timing_path: Path, 
            output_path: Path,
            despawn_offset: int | None,
        ):
        self.solution_dict = self.parse_solution(solution_path)
        self.station_id_dict = self.parse_station_id_map(station_id_map_path)
        self.trips_df = pd.read_csv(trips_path, sep=";")
        self.original_routes = self.parse_routes(routes_path)
        self.deadhead_timings = pd.read_csv(deadhead_timing_path, sep=";")
        self.output_path = output_path
        self.offset = despawn_offset
        # charging events of the solution that could not be turned into a charging stop
        self.unplaced_events = []

    def main(self):
        new_routes = {}

        for bus in self.solution_dict["bus_assignments"]:
            route_id = f"bus_{bus["bus_id"]}"
            trip_edges = []
            trip_stops = []
            previous_original_trip_id = None
            charging_events = sorted(
                (
                    event
                    for event in self.solution_dict["charging_events"]
                    if event["bus_id"] == bus["bus_id"]
                ),
                key=lambda event: event["start_time"]
            )

            for trip in bus["trip_sequence"]:
                original_trip_id = self.trips_df.loc[self.trips_df["TRIP_ID"] == trip, "ORIGINAL_TRIP_ID"].iloc[0]

                if previous_original_trip_id is not None:
                    trip_edges.append(self.build_deadheads(
                        self.original_routes[previous_original_trip_id]["stops"][-1],
                        self.original_routes[original_trip_id]["stops"][0]
                    ))

                trip_edges.append(self.original_routes[original_trip_id]["edges"])

                trip_stops.extend(self.build_stops(trip, original_trip_id, bus["bus_id"], charging_events))

                previous_original_trip_id = original_trip_id

            for event in charging_events:
                self.report_unplaced_event(event, "after the last trip")

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
        if self.unplaced_events:
            logger.warning("%s of %s charging events could not be placed (see warnings above).",
                           len(self.unplaced_events), len(self.solution_dict["charging_events"]))
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
            "until": f"{float(first_stop['until'])
                        - self.deadhead_timings.loc[(self.deadhead_timings['FromStopID'] == start_depot) 
                        & (self.deadhead_timings['ToStopID'] == first_stop['busStop']), 'RunTime'].iloc[0]}",
            "parking": "true",
                        }

        run_time = self.deadhead_timings.loc[
            (self.deadhead_timings["FromStopID"] == last_stop["busStop"])
            & (self.deadhead_timings["ToStopID"] == end_depot),
            "RunTime"
        ].iloc[0]

        arrival_offset = 1800

        if self.offset is None:
            arrival_time = SIMULATION_RUNTIME - arrival_offset
        else:
            arrival_time = min(SIMULATION_RUNTIME- arrival_offset, float(last_stop["until"]) + run_time + self.offset)

        arrival = {
            "busStop": end_depot,
            "until": f"{arrival_time}",
            "parking": "true"
        }

        return start_depot_edges, end_depot_edges, departure, arrival

    def build_stops(self, trip, original_trip_id, route_id, charging_events):
        """Stops of one trip, shifted to its scheduled departure, plus the charging stops planned around it.

        The departure comes from the trip file (VBB schedule), the stop times within the trip from the
        preprocessed routes (SUMO run times). The arrival is therefore taken from the shifted last stop,
        which is the time SUMO and the optimizer use, not from the END_TIMESTAMP of the trip file.
        charging_events (sorted by start) is consumed: placed and unplaceable events are removed."""
        trip_departure_time = int(self.trips_df.loc[self.trips_df["TRIP_ID"] == trip, "START_TIMESTAMP"].iloc[0])

        stops = [dict(stop) for stop in self.original_routes[original_trip_id]["stops"]]
        for stop in stops:
            stop["until"] = str(float(stop["until"]) + trip_departure_time)
            stop["tripId"] = str(trip)
        trip_arrival_time = float(stops[-1]["until"])
        first_stop, last_stop = stops[0]["busStop"], stops[-1]["busStop"]

        # Charging before this trip, at its first stop: every event that ends by the departure.
        # Such an event at another station cannot be placed anymore (its gap between two trips has
        # passed), so it is reported and dropped instead of blocking all later events of the bus.
        placed_before = 0
        while charging_events and charging_events[0]["end_time"] * 60 <= trip_departure_time + TIME_TOLERANCE:
            event = charging_events.pop(0)
            station = self.charging_station(event)
            if station == first_stop:
                stops.insert(placed_before, {
                    "busStop": station,
                    "until": str(int(event["end_time"] * 60)),
                    "tripId": str(trip),
                })
                placed_before += 1
            else:
                self.report_unplaced_event(event, f"before trip {trip}, which starts at {first_stop}")

        # Charging after this trip, at its last stop: the next event, if it starts once the bus has arrived.
        # If not, it stays in the list and is handled as "before the next trip".
        if charging_events:
            event = charging_events[0]
            station = self.charging_station(event)
            if station == last_stop and trip_arrival_time <= event["start_time"] * 60 + TIME_TOLERANCE:
                stops.insert(-1, {
                    "busStop": station,
                    "until": str(int(event["end_time"] * 60)),
                    "duration": str(int(event["end_time"] * 60) - int(event["start_time"] * 60)),
                    "parking": "true",
                    "tripId": str(trip),
                })
                del charging_events[0]

        return stops

    def charging_station(self, event):
        """Bus stop id of the charging station of a charging event."""
        return str(self.station_id_dict.get(str(event["station_id"])))

    def report_unplaced_event(self, event, reason):
        self.unplaced_events.append(event)
        logger.warning("Bus %s: charging event at station %s (%s, %.0f-%.0f s) could not be placed %s.",
                       event["bus_id"], event["station_id"], self.charging_station(event),
                       event["start_time"] * 60, event["end_time"] * 60, reason)

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
