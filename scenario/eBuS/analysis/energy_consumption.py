from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from lxml import etree

class EnergyConsumption:

    def __init__(self, chargingstations_path):

        self.charging_events = self.parse_charging_events(chargingstations_path)

    def parse_charging_events(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        charging_events = []

        for elem in root.iter('chargingEvent'):
            total_energy = float(elem.get('totalEnergyChargedIntoVehicle', 0))

            if total_energy != 0:
                charging_events.append({
                    'station_id': elem.get('chargingStationId'),
                    'vehicle': elem.get('vehicle'),
                    'total_energy': total_energy,
                    'begin_sec': float(elem.get('chargingBegin')),
                    'end_sec': float(elem.get('chargingEnd')),
                })

        charging_events.sort(key=lambda x: x['begin_sec'])
        return charging_events
    
    def calculate_energy_distribution(self):
        opportunity_charging = []
        depot_charging = []
        for chargingEvent in self.charging_events:
            if chargingEvent['station_id'] in ['cd_cicerostrasse_01', 'cd_muellerstrasse_01']:
                depot_charging.append(chargingEvent['total_energy'])
            else:
                opportunity_charging.append(chargingEvent['total_energy'])
        total_ammount_charged = [event['total_energy'] for event in self.charging_events]
        print(f"Total energy charged: {sum(total_ammount_charged)/1000} kWh")
        print(f"Energy charged at depot stations: {sum(depot_charging)/1000} kWh")
        print(f"Energy charged at opportunity stations: {sum(opportunity_charging)/1000} kWh")

    def plot_charging_events(self, save_path=None):
        """
        Line plot of charging events, each drawn from chargingBegin to
        chargingEnd, colored by charging type.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        if not self.charging_events:
            print("No charging event data available.")
            return

        depot_stations = ['cd_cicerostrasse_01', 'cd_muellerstrasse_01']

        plt.figure(figsize=(12, 6))

        colors = {"opportunity": "tab:blue", "depot": "tab:orange"}
        labels = {"opportunity": "Opportunity charging", "depot": "Depot charging"}
        plotted = {"opportunity": False, "depot": False}

        for event in self.charging_events:
            kind = "depot" if event['station_id'] in depot_stations else "opportunity"
            energy = event['total_energy'] / 1000
            plt.plot(
                [event['begin_sec'] / 3600, event['end_sec'] / 3600],
                [energy, energy],
                color=colors[kind],
                alpha=0.7,
                label=labels[kind] if not plotted[kind] else None,
            )
            plotted[kind] = True

        plt.xlabel("Simulation time [h]")
        plt.ylabel("Energy charged [kWh]")
        plt.title("Charging events over time")

        plt.grid(True, alpha=0.3)
        plt.legend(title="Charging type")
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()
