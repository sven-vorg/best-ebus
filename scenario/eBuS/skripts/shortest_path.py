import sumolib

# Read Network
NETWORK = "best-ebus/scenario/sumo/berlin.net.xml"
net = sumolib.net.readNet(NETWORK)

path, _ = net.getFastestPath(
    net.getEdge("30157290"),
    net.getEdge("151043332#5"),
    includeFromToCost=False,
)

print(" ".join(edge.getID() for edge in path))
