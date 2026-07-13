""" 
timestep_time;
vehicle_acceleration;
vehicle_actualBatteryCapacity;
vehicle_chargingStationId;
vehicle_energyCharged;
vehicle_energyChargedInTransit;
vehicle_energyChargedStopped;
vehicle_energyConsumed;
vehicle_id;
vehicle_lane;
vehicle_maximumBatteryCapacity;
vehicle_posOnLane;
vehicle_speed;
vehicle_timeStopped;
vehicle_totalEnergyConsumed;
vehicle_totalEnergyRegenerated;
vehicle_x;
vehicle_y

chargingStation_chargingSteps;
chargingStation_id;
chargingStation_totalEnergyCharged;
vehicle_chargingBegin;
vehicle_chargingEnd;
vehicle_id;
vehicle_totalEnergyChargedIntoVehicle;
vehicle_type;
step_actualBatteryCapacity;
step_chargingStatus;
step_efficiency;
step_energyCharged;
step_maximumBatteryCapacity;
step_partialCharge;
step_power;step_time
"""

import pandas as pd

class CalculateEnergy():

    def __init__(
            self,
            battery: str = "best-ebus/scenario/sumo/output/electric_bus_2026-07-13-20-31-12_battery.csv",
            chargingstations: str = "best-ebus/scenario/sumo/output/electric_bus_2026-07-13-20-31-12_chargingsstations.csv"
            ):
        self.battery = pd.read_csv(battery)
        self.chargingstations = pd.read_csv(chargingstations)

    def _inspect(self):
        print(self.battery.head())
        print(self.chargingstations.head())

    def main(self):
        print("Running")
        self._inspect()

    def _group_sixty():
        pass

if __name__ == "__main__":
    ce = CalculateEnergy()
    ce.main()