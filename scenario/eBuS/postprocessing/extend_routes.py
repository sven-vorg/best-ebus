import copy
from lxml import etree
from pathlib import Path
from operator import itemgetter
from collections import defaultdict

DAY = 86400


class ExtendRoutes:

    def __init__(self,
        routes_path: Path,
        vehicles_path: Path
        ):
        self.routes_root = self._load_xml(routes_path)
        self.vehicles_root = self._load_xml(vehicles_path)
        self.route_types = self._build_route_type_map()
        self.route_elems = {r.get("id"): r for r in self.routes_root.iter("route")}

    def main(self, output_path: Path, days: int):
        routes_list = self.get_routes_list()
        info = {r["id"]: r for r in routes_list}
        depots = self._match_arrival_and_departure_depot(routes_list)

        pairs = []
        for depot, lists in depots.items():
            types = {r["type"] for r in lists["arrivals"] + lists["departures"]}
            for vtype in types:
                arrivals = [r for r in lists["arrivals"] if r["type"] == vtype]
                departures = [r for r in lists["departures"] if r["type"] == vtype]
                print(f"--- {depot} / {vtype} ---")
                pairs.extend(self.match_fifo_routes(arrivals, departures))

        # arriving id -> id of the route it is followed by
        partner = {arriving["id"]: leaving["id"] for arriving, leaving in pairs}

        new_routes = [
            self.build_multiday_route(route_id, partner, info, days)
            for route_id in partner
        ]
        for route in new_routes:
            self.clean_route(route)
        self.write_xml(new_routes, output_path)

    def _load_xml(self, xml_path: Path):
        return etree.parse(xml_path).getroot()

    def _match_arrival_and_departure_depot(self, routes_list: list) -> dict:
        """depot -> {"arrivals": [...], "departures": [...]}, each sorted by time."""
        depots = defaultdict(lambda: {"arrivals": [], "departures": []})
        for route in routes_list:
            depots[route["arrival_depot"]]["arrivals"].append(route)
            depots[route["departure_depot"]]["departures"].append(route)

        for lists in depots.values():
            lists["arrivals"].sort(key=itemgetter("arrives_depot"))
            lists["departures"].sort(key=itemgetter("leaves_depot"))
        return depots


    def _build_route_type_map(self) -> dict[str, str]:
        """route id -> vType id, built once from the vehicles file."""
        return {
            vehicle.get("route"): vehicle.get("type")
            for vehicle in self.vehicles_root.iter("vehicle")
            if vehicle.get("route") is not None
        }

    def get_routes_list(self) -> list:
        routes = []
        for route in self.routes_root.iter("route"):
            stop_elems = route.findall("stop")
            if not stop_elems:
                continue
            first_until = stop_elems[0].get("until")
            last_until = stop_elems[-2].get("until")
            if first_until is None or last_until is None:
                continue  # stop without "until" (e.g. only "duration")
            routes.append({
                "id": route.get("id"),
                "type": self.route_types.get(route.get("id")),
                "leaves_depot": float(first_until),
                "arrives_depot": float(last_until),
                "departure_depot": stop_elems[0].get("busStop"),
                "arrival_depot": stop_elems[-1].get("busStop"),
            })
        return routes

    def match_fifo_routes(self, arrivals: list, departures: list) -> list:
        arrivals = sorted(arrivals, key=itemgetter("arrives_depot"))
        departures = sorted(departures, key=itemgetter("leaves_depot"))

        if len(arrivals) != len(departures):
            print(f"WARNING: {len(arrivals)} arrivals vs {len(departures)} departures, "
                f"{abs(len(arrivals) - len(departures))} route(s) stay unmatched")

        pairs = list(zip(arrivals, departures))
        for arriving, leaving in pairs:
            print(f"  {arriving['id']} ({arriving['arrives_depot']}) -> "
                f"{leaving['id']} ({leaving['leaves_depot']})")
        return pairs

    def build_multiday_route(self, route_id: str, partner: dict, info: dict, days: int) -> etree._Element:
        route = copy.deepcopy(self.route_elems[route_id])      # day 0, keeps its id
        edges = [route.get("edges")]
        current = route_id

        for day in range(1, days):
            if current not in partner:
                print(f"WARNING: {route_id} has no partner after {current}, "
                    f"route only covers {day} day(s)")
                break
            current = partner[current]
            offset = day * DAY

            nxt = copy.deepcopy(self.route_elems[current])
            for stop in nxt.findall("stop"):
                until = stop.get("until")
                if until is not None:
                    stop.set("until", str(float(until) + offset))

            # depot stop of the previous day lasts until the shifted departure of the next route
            route.findall("stop")[-1].set("until", str(info[current]["leaves_depot"] + offset))

            edges.append(nxt.get("edges"))
            for stop in nxt.findall("stop"):
                route.append(stop)

        route.set("edges", " ".join(edges))
        return route

    def write_xml(self, new_routes: list, output_path: Path):
        root = etree.Element("routes", nsmap=self.routes_root.nsmap)
        for new_route in new_routes:
            root.append(new_route)

        etree.ElementTree(root).write(
            str(output_path), pretty_print=True, xml_declaration=True, encoding="UTF-8"
        )
        print(f"Wrote {len(new_routes)} routes to {output_path}")

    def remove_duplicate_edges(self, edges: list):
        all_edges = [edge for group in edges for edge in group.split()]
        deduplicated_edges = [
            edge for i, edge in enumerate(all_edges)
            if i == 0 or edge != all_edges[i - 1]
        ]
        edges[:] = deduplicated_edges          # unchanged

    def remove_duplicate_stops(self, stops: list):
        if not stops:
            return

        deduplicated_stops = [stops[0]]
        for stop in stops[1:]:
            previous_stop = deduplicated_stops[-1]
            if stop.get("busStop") != previous_stop.get("busStop"):
                deduplicated_stops.append(stop)
                continue

            if stop.get("station_id") is not None:
                if float(previous_stop.get("until")) > float(stop.get("until")):
                    stop.set("until", previous_stop.get("until"))
                deduplicated_stops[-1] = stop
            elif previous_stop.get("station_id") is not None:
                if float(stop.get("until")) > float(previous_stop.get("until")):
                    previous_stop.set("until", stop.get("until"))
            elif float(stop.get("until")) > float(previous_stop.get("until")):
                deduplicated_stops[-1] = stop

        stops[:] = deduplicated_stops          # same list-mutation trick as yours

    def clean_route(self, route: etree._Element):
        # edges: the attribute is one string, so wrap it in a list for your function
        edges = [route.get("edges")]
        self.remove_duplicate_edges(edges)
        route.set("edges", " ".join(edges))

        # stops: dedupe, then remove the dropped elements from the route
        stops = route.findall("stop")
        kept = list(stops)
        self.remove_duplicate_stops(kept)
        for stop in stops:
            if stop not in kept:
                route.remove(stop)


if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent
    routes_path = (HERE / "../../sumo/electric/e_routes.rou.xml").resolve()
    vehicles_path = (HERE / "../../sumo/electric/e_vehicles.rou.xml").resolve()
    output_path = (HERE / "../../sumo/electric/e_routes_extended.rou.xml").resolve()
    ExtendRoutes(routes_path, vehicles_path).main(output_path, days=5)