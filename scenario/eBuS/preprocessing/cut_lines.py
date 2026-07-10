# Imports
from pathlib import Path
from lxml import etree

class CutLines():

    def __init__(self, 
        stations_path: str = "best-ebus/scenario/sumo/berlin_bus_stops.add.xml",
        routes_path: str = "best-ebus/scenario/ebus/files/cicero_mueller_routes.rou.xml",
        output_path: str = "best-ebus/scenario/ebus/files/cicero_mueller_routes_trimmed.rou.xml"
        ):
        self.stations_path = Path(stations_path)
        self.routes_path = Path(routes_path)
        self.output_path = Path(output_path)

    def _load_xml(self):
        self.stations_root = etree.parse(self.stations_path).getroot()

        self.routes_tree = etree.parse(self.routes_path)
        self.routes_root = self.routes_tree.getroot() 

    def _trim_route_edges(self, edges, start_edge, end_edge):
        """Returns the subsection of a route between two edges."""
        route_edges = edges.split()

        start_index = route_edges.index(start_edge)
        end_index = len(route_edges) - 1 - route_edges[::-1].index(end_edge)

        return " ".join(route_edges[start_index:end_index + 1])

    def trim_routes(self):
        self._load_xml()
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
        self._write_to_xml()

    def _write_to_xml(self):
        self.routes_tree.write(
        self.output_path,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    )



if __name__ == "__main__":
    cl = CutLines()
    cl.trim_routes()