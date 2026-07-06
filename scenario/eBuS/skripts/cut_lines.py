# Imports
from lxml import etree
import sumolib
import pandas as pd
import os

class CutLines():

    def __init__(self):
        STATIONS = "best-ebus/scenario/ebus/files/termination_points.add.xml"
        self.stations_tree = etree.parse(STATIONS)
        self.stations_root = self.stations_tree.getroot()

        self.ROUTES = "best-ebus/scenario/ebus/files/cicero_mueller_routes.rou.xml"
        self.routes_tree = etree.parse(self.ROUTES)
        self.routes_root = self.routes_tree.getroot()

    
    def main(self):

        for route in self.routes_root.findall("route"):
            stops = route.findall("stop")
            first_stop = stops[0].get("busStop")
            last_stop = stops[-1].get("busStop")

            first_station = self.stations_root.find(f".//chargingStation[@id='{first_stop}']")
            last_station = self.stations_root.find(f".//chargingStation[@id='{last_stop}']")

            first_edge = first_station.get("lane").rsplit("_", 1)[0]
            last_edge = last_station.get("lane").rsplit("_", 1)[0]


            edges = route.get("edges").split()
            start = edges.index(first_edge)
            end = edges.index(last_edge)
            trimmed_edges = " ".join(edges[start:end + 1])

            route.set("edges", trimmed_edges)

        #os.remove(self.ROUTES)

        self.routes_tree.write(
        "best-ebus/scenario/ebus/files/cicero_mueller_routes_trimmed.rou.xml",
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
)



if __name__ == "__main__":
    cl = CutLines()
    cl.main()