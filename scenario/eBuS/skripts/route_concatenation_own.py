"""
route_concatenation.py

Builds two linked SUMO route files from an optimizer's bus assignment
solution (solution_cicerostrasse.json), stitching each bus's trip sequence
together with the deadhead edges that connect the depot to the first
stop, between consecutive trips, and back to the depot.

Entry point:
    main() -> builds everything in memory, rebases stop "until"
               timestamps, sorts vehicles by depart time, and writes two
               files:
                 - ROUTES_OUTPUT:   one <route id=... edges=...> per bus,
                                    each carrying its ordered <stop>s
                 - VEHICLES_OUTPUT: one <vehicle> per bus, referencing its
                                    route via route="<route id>"

Each generated <route> carries the ordered passenger <stop> elements of
its real trips (deadhead legs contribute none), with their "until"
timestamps re-based so they increase monotonically across the whole
concatenated route instead of resetting at each original trip boundary.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from lxml import etree

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class RouteConcatenation:
    """Builds linked SUMO route + vehicle files from an optimized bus-assignment solution."""

    #: id used to anchor deadhead edges ("<DEPOT_ID>_<stop>" / "<stop>_<DEPOT_ID>")
    DEPOT_ID = "1"

    def __init__(
        self,
        input_path: str = "./best-ebus/scenario/eBuS/files/solution_cicerostrasse.json",
        input_dict: str = "./best-ebus/scenario/eBuS/files/trips_cicerostrasse.txt",
        chargers_dict: str = "/best-ebus/scenario/eBuS/files/charging_stations.txt",
        routes_path: str = "./best-ebus/scenario/eBuS/files/merged_deadheads_routes.rou.xml",
        routes_output_path: str = "./best-ebus/scenario/sumo/electric/e_routes.rou.xml",
        vehicles_output_path: str = "./best-ebus/scenario/sumo/electric/e_vehicles.rou.xml",
    ) -> None:
        self.INPUT = Path(input_path)
        self.ROUTES = Path(routes_path)
        self.ROUTES_OUTPUT = Path(routes_output_path)
        self.VEHICLES_OUTPUT = Path(vehicles_output_path)

        self._load_trip_dictionary(input_dict)
        self._load_route_lookups()

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _load_trip_dictionary(self, input_dict: str) -> None:
        """
        Parse trips_cicerostrasse.txt into per-trip lookup dicts.

        The file maps every TRIP_ID to its original SUMO trip id, its
        start/end stop, and its scheduled departure timestamp.
        """
        trip_df = pd.read_csv(input_dict, sep=";").set_index("TRIP_ID")
        self.trip_to_original: dict[Any, Any] = trip_df["ORIGINAL_TRIP_ID"].to_dict()
        self.trip_to_start: dict[Any, Any] = trip_df["START_STOP_ID"].to_dict()
        self.trip_to_end: dict[Any, Any] = trip_df["END_STOP_ID"].to_dict()
        self.trip_to_depart: dict[Any, Any] = trip_df["START_TIMESTAMP"].to_dict()

    def _load_route_lookups(self) -> None:
        """
        Parse merged_deadheads_routes.rou.xml into:
            route_lookup: id -> {"edges": str, "stops": [stop_dict, ...]}

        This covers both real trip routes (which have <stop> children with
        passenger-stop info) and "<a>_<b>" deadhead connector routes (which
        have edges but no <stop> children, so "stops" is just an empty list).
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

    def _load_chargers_dict(self, chargers_dict: str):
        self.chargers = pd.read_csv(chargers_dict)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    def main(self) -> None:
        """
        Read the optimizer solution and write:
          - one <route> per bus (with its stops) to ROUTES_OUTPUT
          - one <vehicle> per bus, referencing that route, to VEHICLES_OUTPUT
        """
        with self.INPUT.open("r") as f:
            solution = json.load(f)

        nsmap = {"xsi": "http://www.w3.org/2001/XMLSchema-instance"}
        routes_root = etree.Element("routes", nsmap=nsmap)
        vehicles_root = etree.Element("routes", nsmap=nsmap)
        etree.SubElement(vehicles_root, "vType", id="bus", vClass="bus")

        for bus in solution["bus_assignments"]:
            trip_sequence = bus["trip_sequence"]
            route_id = f"cicero_{bus['bus_id']}_route"

            route = etree.SubElement(
                routes_root,
                "route",
                id=route_id,
                edges=self.join_edges_by_route_id(trip_sequence),
            )
            for stop in self.join_stops_by_route_id(trip_sequence):
                etree.SubElement(route, "stop", **self._stop_attributes(stop))

            etree.SubElement(
                vehicles_root,
                "vehicle",
                id=f"cicero_{bus['bus_id']}",
                # Do the conversion to electric here?
                type="Ebusco2.2electric12m",
                route=route_id,
                depart=str(self.trip_to_depart[trip_sequence[0]]),
                color="1,0,0",
            )

        # Trip-local "until" timestamps reset at each original trip boundary;
        # rebase them so each route's stops increase monotonically.
        self.adapt_until_values(routes_root)

        # Sort vehicles by depart time before writing.
        self._sort_vehicles_by_depart(vehicles_root)

        self._write(routes_root, self.ROUTES_OUTPUT)
        self._write(vehicles_root, self.VEHICLES_OUTPUT)

    @staticmethod
    def _write(root: etree.Element, path: Path) -> None:
        """Write an lxml element tree to `path`, creating parent dirs as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        etree.ElementTree(root).write(
            str(path),
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
        )
        logger.info("Wrote %s", path)
        print(f"Written {path} to disk.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _sort_vehicles_by_depart(routes: etree.Element) -> None:
        """Reorder the <vehicle> children of `routes` in place by ascending depart time."""
        vehicles = routes.findall("vehicle")
        for vehicle in vehicles:
            routes.remove(vehicle)

        vehicles.sort(key=lambda v: float(v.get("depart")))
        for vehicle in vehicles:
            routes.append(vehicle)

    def join_edges_by_route_id(self, trip_ids: list) -> str:
        """
        Build one continuous edge string for a bus by chaining:
            depot -> first trip's start        (deadhead)
            for every trip: trip start -> trip end, then
                (if another trip follows) trip end -> next trip's start
            last trip's end -> depot            (deadhead)

        Consecutive duplicate edges are then collapsed.
        """
        depart_station = self.DEPOT_ID
        edges = []
        for trip_id in trip_ids:
            edges.append(self.route_lookup[f"{depart_station}_{self.trip_to_start[trip_id]}"]["edges"])
            original_trip_id = self.trip_to_original[trip_id]
            edges.append(self.route_lookup[original_trip_id]["edges"])
            depart_station = self.trip_to_end[trip_id]
        edges.append(self.route_lookup[f"{depart_station}_{self.DEPOT_ID}"]["edges"])
        return self._remove_consecutive_duplicates(" ".join(edges))

    def join_stops_by_route_id(self, trip_ids: list) -> list[dict]:
        """
        Collect the ordered passenger stops for a bus's full trip sequence.

        Only real trip routes carry passenger stops; deadhead connector
        routes (depot <-> stop) contribute nothing, so this walks the
        original trip ids only rather than the full edge-joining sequence.
        """
        stops: list[dict] = []
        for trip_id in trip_ids:
            original_trip_id = self.trip_to_original[trip_id]
            stops.extend(self.route_lookup[original_trip_id]["stops"])
        return stops

    def adapt_until_values(self, routes_root: etree.Element) -> None:
        """
        Rebase each route's stop "until" timestamps so they increase
        monotonically across the whole concatenated route.

        Each original trip's "until" values are relative to that trip
        alone, so once several trips are chained into one route the values
        reset (drop) at every trip boundary. This walks each route's stops
        in order, detects a reset (an "until" smaller than the one
        before it), and from that point on adds an offset equal to the
        last adjusted "until" value so the timeline keeps increasing.
        """
        for route in routes_root.findall("route"):
            offset = 0.0
            previous_original_until = None
            previous_adjusted_until = None

            for stop in route.findall("stop"):
                original_until = float(stop.get("until"))

                if (
                    previous_original_until is not None
                    and original_until < previous_original_until
                ):
                    offset = previous_adjusted_until

                adjusted_until = original_until + offset
                stop.set("until", str(adjusted_until))

                previous_original_until = original_until
                previous_adjusted_until = adjusted_until

    @staticmethod
    def _stop_attributes(stop: dict) -> dict[str, str]:
        """
        Build the string attribute dict for a <stop> element, omitting
        "duration"/"until" when unset instead of writing the literal
        string "None" (a bug in the reference implementation this is
        based on).
        """
        attrs = {"busStop": stop["busStop"], "parking": str(stop["parking"]).lower()}
        if stop["duration"] is not None:
            attrs["duration"] = str(stop["duration"])
        if stop["until"] is not None:
            attrs["until"] = str(stop["until"])
        return attrs

    @staticmethod
    def _remove_consecutive_duplicates(edge_string: str) -> str:
        """Collapse consecutive duplicate edge ids, e.g. 'a a b b b c' -> 'a b c'."""
        edges = edge_string.split()
        deduped: list[str] = []
        for edge in edges:
            if not deduped or deduped[-1] != edge:
                deduped.append(edge)
        return " ".join(deduped)


if __name__ == "__main__":
    rc = RouteConcatenation()
    rc.main()
