# Imports
from pathlib import Path
from lxml import etree

class CutLines():

    def __init__(self,
        stations_path: Path,
        routes_root
        ):
        self.stations_path = Path(stations_path)
        self.routes_root = routes_root

    def _load_stations(self):
        self.stations_root = etree.parse(self.stations_path).getroot()

    def _trim_route_edges(self, edges, start_edge, end_edge):
        """Returns the subsection of a route between two edges."""
        route_edges = edges.split()

        start_index = route_edges.index(start_edge)
        end_index = len(route_edges) - 1 - route_edges[::-1].index(end_edge)

        return " ".join(route_edges[start_index:end_index + 1])

    def trim_routes(self):
        self._load_stations()
        for route in self.routes_root.findall("route"):
            stops = route.findall("stop")
            first_stop = stops[0].get("busStop")
            last_stop = stops[-1].get("busStop")

            first_station = self.stations_root.find(f".//busStop[@id='{first_stop}']")
            last_station = self.stations_root.find(f".//busStop[@id='{last_stop}']")

            first_edge = first_station.get("lane").rsplit("_", 1)[0]
            last_edge = last_station.get("lane").rsplit("_", 1)[0]

            trimmed = self._trim_route_edges(
                route.get("edges"),
                first_edge,
                last_edge
            )

            route.set("edges", trimmed)
        return self.routes_root

    def write_to_xml(self, output_path: Path):
        """Debug helper for standalone runs; not used by the pipeline."""
        etree.ElementTree(self.routes_root).write(
            output_path,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8"
        )


if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent
    stations_path: Path = (HERE / "../../sumo/berlin_bus_stops.add.xml")
    routes_path: Path = HERE / "../files/cicero_mueller_routes.rou.xml"
    output_path: Path = HERE / "../files/cicero_mueller_routes_trimmed.rou.xml"
    routes_root = etree.parse(routes_path).getroot()
    cl = CutLines(stations_path, routes_root)
    cl.trim_routes()
    cl.write_to_xml(output_path)