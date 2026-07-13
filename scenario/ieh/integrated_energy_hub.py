# In Therory extends sumo chargingStation
class IntegratedEnergyHub():

    def __init__(
        self, 
        id, 
        name, 
        lane, 
        starPos, 
        endPos, 
        power, 
        effciency, 
        chargeInTransit, 
        friendlyPos, 
        coordinates, 
        essCapacity: float = 500.00,
        ):
        self.essCapacity = essCapacity
