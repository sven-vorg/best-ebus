# Imports
from charging_stations import ChargingStations
from route_concatenation import RouteConcatenation

class HeuristicPostprocessing:
    def __init__(self):
        pass

    def main(self):
        # Create e_stations.add.xml containing stations designated as charging opportunitys
        cs = ChargingStations()
        cs.main()

        # Work in Progress
        # pv for stations

        # Create the combined routes for all electric buses in the simulation
        rc = RouteConcatenation()
        rc.main()

if __name__ == "__main__":
    hp = HeuristicPostprocessing()
    hp.main()

