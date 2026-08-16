from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from lxml import etree

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class BuildRoutes:
    """Builds linked SUMO route files from an optimized bus-assignment solution."""

    def __init__(
        self,
        solution_path: Path,
        tripp_dict: Path,
        deadhead_path: Path,
        merged_routes: Path,
        e_routes_output: Path
    ) -> None:
        self.SOLUTION = solution_path
        self.ROUTES = merged_routes
        self.ROUTES_OUTPUT = e_routes_output


        # Set available depots
        self.DEPOTS = {
                1: "bs_cicerostrasse",
                2: "bs_muellerstrasse"
            }

        self._load_trip_dictionary(tripp_dict)
        self._load_deadhead_dictionary(deadhead_path)
        self._load_route_lookups()

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _load_trip_dictionary(self, tripp_dict: Path) -> None:
        """
        Parse trips_vbb.txt into per-trip lookup dicts.

        The file maps every TRIP_ID to its original SUMO trip id, its
        start/end stop, and its scheduled departure/arrival timestamps.
        """
        trip_df = pd.read_csv(tripp_dict, sep=";").set_index("TRIP_ID")
        self.trip_to_original: dict[Any, Any] = trip_df["ORIGINAL_TRIP_ID"].to_dict()
        self.trip_to_start: dict[Any, Any] = trip_df["START_STOP_ID"].to_dict()
        self.trip_to_end: dict[Any, Any] = trip_df["END_STOP_ID"].to_dict()
        self.trip_to_depart: dict[Any, Any] = trip_df["START_TIMESTAMP"].to_dict()
        self.trip_to_arrival: dict[Any, Any] = trip_df["END_TIMESTAMP"].to_dict()

    def _load_route_lookups(self) -> None:
        """
        Parse merged_deadheads_routes.rou.xml into:
            route_lookup: id -> {"edges": str, "stops": [stop_dict, ...]}
        """
        route_root = etree.parse(str(self.ROUTES)).getroot()

        self.route_lookup: dict[str, dict[str, Any]] = {
            route.get("id"): {
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
            for route in route_root.findall("route")
        }

    def _load_deadhead_dictionary(self, deadhead_path: Path):
        self.stations_to_time = {}

        with deadhead_path.open("r", encoding="utf-8") as f:
            next(f)  # skip header

            for line in f:
                from_stop_id, to_stop_id, runtime = line.strip().split(";")
                self.stations_to_time[(from_stop_id, to_stop_id)] = int(runtime)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    def main(self) -> None:
        """
        Read the optimizer solution and write:
          - one <route> per bus (with its stops) to ROUTES_OUTPUT
        """

        with self.SOLUTION.open("r") as f:
            solution = json.load(f)

        nsmap = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
        routes_root = etree.Element("routes", nsmap=nsmap)

        for bus in solution["bus_assignments"]:
            # Contains all trips of a bus from the solution
            trip_sequence: list = bus["trip_sequence"]

            start_depot = self.DEPOTS[bus["start_depot"]]
            end_depot = self.DEPOTS[bus["end_depot"]]
            route_id = f"{bus['bus_id']}_route"

            route = etree.SubElement(
                routes_root,
                "route",
                id=route_id,
                edges=self.join_edges_by_route_id(trip_sequence, start_depot=start_depot, end_depot=end_depot),
            )

            stops = self.join_stops_by_route_id(trip_sequence, start_depot=start_depot, end_depot=end_depot)
            for stop in self.join_stops_by_route_id(trip_sequence, start_depot=start_depot, end_depot=end_depot):
                etree.SubElement(route, "stop", attrib=stop)

        self._write_xml(routes_root, self.ROUTES_OUTPUT)
        logger.info("Wrote %s", self.ROUTES_OUTPUT)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def join_edges_by_route_id(self, trip_ids: list, start_depot: str, end_depot: str) -> str:
        """
        Build one continuous edge string for a bus by chaining:
            depot -> first trip's start        (deadhead)
            for every trip: trip start -> trip end, then
                (if another trip follows) trip end -> next trip's start
            last trip's end -> depot            (deadhead)

        Consecutive duplicate edges are then collapsed.
        """
        depart_station = start_depot
        edges = []
        for trip_id in trip_ids:
            edges.append(self.route_lookup[f"{depart_station}_{self.trip_to_start[trip_id]}"]["edges"])
            original_trip_id = self.trip_to_original[trip_id]
            edges.append(self.route_lookup[original_trip_id]["edges"])
            depart_station = self.trip_to_end[trip_id]
        edges.append(self.route_lookup[f"{depart_station}_{end_depot}"]["edges"])
        return self._remove_consecutive_duplicates(" ".join(edges))

    def join_stops_by_route_id(self, trip_ids: list, start_depot: str, end_depot: str) -> list[dict]:
        # Variable storing stops
        stops: list[dict] = []
        # Set departure at depot
        departure_time = (
            self.trip_to_depart[trip_ids[0]]
            - self.stations_to_time[
                (start_depot, self.trip_to_start[trip_ids[0]])
            ]
        )
        stops.append({
            "busStop": start_depot,
            "parking": "true",
            "duration": str(departure_time),
            "until": str(departure_time),
        })


        for trip_id in trip_ids:
            original_trip_id = self.trip_to_original[trip_id]
            start_timestamp = self.trip_to_depart[trip_id]
            for stop in self.route_lookup[original_trip_id]["stops"]:
                stops.append({
                    "busStop": str(stop["busStop"]),
                    "parking": str(stop["parking"]),
                    "duration": str(stop["duration"]),
                    "until": str(stop["until"] + start_timestamp),
                })

        # Set arrival at depot
        stops.append({
            "busStop": end_depot,
            "parking": "true",
            "duration": "0",
            "until": "104400",
        })
        
        return stops

    @staticmethod
    def _remove_consecutive_duplicates(edge_string: str) -> str:
        """Collapse consecutive duplicate edge ids, e.g. 'a a b b b c' -> 'a b c'."""
        edges = edge_string.split()
        deduped: list[str] = []
        for edge in edges:
            if not deduped or deduped[-1] != edge:
                deduped.append(edge)
        return " ".join(deduped)

    def _write_xml(self, root: etree.Element, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        etree.ElementTree(root).write(
            str(path),
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
        )

if __name__ == "__main__":

    HERE = Path(__file__).resolve().parent
    solution_path = Path(HERE / "../files/postprocessing_input/solution.json").resolve()
    tripp_dict = Path(HERE / "../files/postprocessing_input/trips_vbb.txt").resolve()
    deadhead_timings = Path(HERE / "../files/postprocessing_input/deadhead_times.txt").resolve()
    routes_path = Path(HERE / "../files/merged_routes.rou.xml").resolve()
    routes_output_path = Path(HERE / "../../sumo/electric/e_routes.rou.xml").resolve()
    br = BuildRoutes(solution_path, tripp_dict, deadhead_timings, routes_path, routes_output_path)
    br.main()
