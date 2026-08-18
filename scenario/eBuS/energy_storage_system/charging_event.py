class ChargingEvent:
    __slots__ = (
        'vehicle', 
        'total_energy', 
        'begin_sec', 
        'end_sec', 
        'energy_per_minute'
        )
    def __init__(self, vehicle, total_energy, begin_sec, end_sec):
        self.vehicle = vehicle
        self.total_energy = total_energy   # Wh
        self.begin_sec = begin_sec
        self.end_sec = end_sec
        self.energy_per_minute = 0.0