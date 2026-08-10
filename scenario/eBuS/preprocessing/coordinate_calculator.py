""" Skript for adding coordinates as custom xml parameter to berlin_bus_stops.add.xml """

from lxml import etree
import pandas as pd
import sumolib
from pathlib import Path
from sumolib.geomhelper import positionAtShapeOffset

class CoordinateCalculator:

    def __init__(self, net_file_path, bus_stops_file_path):
        self.net_file_path = net_file_path
        self.bus_stops_file_path = bus_stops_file_path

        # Load the SUMO network
        self.net = sumolib.net.readNet(self.net_file_path)

        # Load the bus stops XML
        self.bus_stops_tree = etree.parse(self.bus_stops_file_path)
        self.bus_stops_root = self.bus_stops_tree.getroot()

    def add_coordinates_to_bus_stops(self):
        for stop in self.bus_stops_root.findall("busStop"):
            lane_id = stop.get("lane")
            pos = float(stop.get("pos", 0))

            lane = self.net.getLane(lane_id)
            if lane is None:
                continue  # skip stops referencing an unknown lane

            shape = lane.getShape()
            x, y = positionAtShapeOffset(shape, pos)
            lon, lat = self.net.convertXY2LonLat(x, y)

            stop.set("coordinates", f"{lon:.6f},{lat:.6f}")

        return self.bus_stops_tree

    def save(self, output_path=None):
        output_path = output_path or self.bus_stops_file_path
        self.bus_stops_tree.write(
            output_path,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )

if __name__ == "__main__":
    net_file_path = "best-ebus/scenario/sumo/berlin.net.xml"
    bus_stops_file_path = "best-ebus/scenario/sumo/berlin_bus_stops.add.xml"
    coordinate_calculator = CoordinateCalculator(net_file_path, bus_stops_file_path)
    coordinate_calculator.add_coordinates_to_bus_stops()
    coordinate_calculator.save()