import sumolib
from lxml import etree
from sumolib.geomhelper import positionAtShapeOffset

net = sumolib.net.readNet("best-ebus/scenario/sumo/berlin.net.xml")
tree = etree.parse("best-ebus/scenario/sumo/electric/e_stations.add.xml")
root = tree.getroot()

def station_to_geo(net, root):
    for station in root.findall(".//chargingStation"):
        lane_id = station.get("lane")
        pos = float(station.get("pos", 0))

        lane = net.getLane(lane_id)
        shape = lane.getShape()

        # position along the lane's shape -> network x,y
        x, y = positionAtShapeOffset(shape, pos)

        # network x,y -> lon/lat (WGS84)
        lon, lat = net.convertXY2LonLat(x, y)

        station.set("coordinates", f"{lon:.6f},{lat:.6f}")

    return root

station_to_geo(net, root)

tree.write(
    "best-ebus/scenario/sumo/electric/e_stations.add.xml",
    pretty_print=True,
    xml_declaration=True,
    encoding="UTF-8",
)