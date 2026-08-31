# AI generated on 2026-08-18
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from lxml import etree


class VehicleSOC:

    DEPOT_STATIONS = ('cd_cicerostrasse_01', 'cd_muellerstrasse_01')

    # Fixed, colorblind-safe categorical palette, in a validated non-cycling
    # order. Past this many vTypes, extra series would need to fold into
    # "Other" rather than repeat a color. Kept in sync with TripInfo.PALETTE.
    PALETTE = [
        '#2a78d6',  # blue
        '#eb6834',  # orange
        '#1baf7a',  # aqua
        '#eda100',  # yellow
        '#e87ba4',  # magenta
        '#008300',  # green
        '#4a3aa7',  # violet
        '#e34948',  # red
    ]

    def __init__(self, battery_path):

        self.battery_data = self.parse_battery(battery_path)

    def parse_battery(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()

        records = []

        for timestep in root.iter('timestep'):
            time_sec = float(timestep.get('time'))

            for vehicle in timestep.iter('vehicle'):
                actual_capacity = float(vehicle.get('actualBatteryCapacity'))
                max_capacity = float(vehicle.get('maximumBatteryCapacity'))
                station_id = vehicle.get('chargingStationId')

                records.append({
                    'time_sec': time_sec,
                    'vehicle': vehicle.get('id'),
                    'actual_capacity': actual_capacity,
                    'max_capacity': max_capacity,
                    'soc': actual_capacity / max_capacity * 100 if max_capacity else float('nan'),
                    'charging_station_id': None if station_id == 'NULL' else station_id,
                })

        df = pd.DataFrame.from_records(records)
        df.sort_values(['vehicle', 'time_sec'], inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    def parse_vtypes(self, tripinfo_path):
        """
        Build a {vehicle_id: vType} mapping from a tripinfo XML file.
        """

        tree = etree.parse(tripinfo_path)
        root = tree.getroot()

        return {
            trip.get('id'): trip.get('vType')
            for trip in root.iter('tripinfo')
        }

    def plot_soc_over_time(self, tripinfo_path, save_path=None):
        """
        Plot the state of charge of every bus over the course of the
        day, one line per bus, colored by vehicle type (vType).

        Parameters
        ----------
        tripinfo_path : str or Path
            Path to the tripinfo XML file, used to look up each
            vehicle's vType (not present in the battery data itself).
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        if self.battery_data.empty:
            print("No battery data available.")
            return

        vtype_by_vehicle = self.parse_vtypes(tripinfo_path)

        df = self.battery_data.copy()
        df['vtype'] = df['vehicle'].map(vtype_by_vehicle)

        vtypes = sorted(df['vtype'].dropna().unique())

        if not vtypes:
            print("No matching vehicle types found in tripinfo data.")
            return

        if len(vtypes) > len(self.PALETTE):
            print(
                f"Warning: {len(vtypes)} vehicle types exceed the "
                f"{len(self.PALETTE)}-color palette; colors will repeat."
            )

        color_map = {
            vtype: self.PALETTE[i % len(self.PALETTE)]
            for i, vtype in enumerate(vtypes)
        }

        plt.figure(figsize=(12, 6))

        for vtype in vtypes:
            subset = df[df['vtype'] == vtype]

            for i, (_, veh_data) in enumerate(subset.groupby('vehicle')):
                plt.plot(
                    veh_data['time_sec'] / 3600,
                    veh_data['soc'],
                    color=color_map[vtype],
                    linewidth=0.8,
                    alpha=0.6,
                    label=vtype if i == 0 else None,
                )

        plt.xlabel("Simulation time [h]")
        plt.ylabel("State of charge [%]")
        plt.title("State of charge of every bus over time")

        plt.grid(True, alpha=0.3)
        plt.legend(title="Vehicle type")
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def plot_cumulative_soc(self, save_path=None):
        """
        Plot the cumulative (summed) battery energy of all buses
        over the course of the day.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        if self.battery_data.empty:
            print("No battery data available.")
            return

        cumulative = (
            self.battery_data
            .groupby('time_sec')['actual_capacity']
            .sum() / 1000  # Wh -> kWh
        )

        times_h = cumulative.index / 3600

        plt.figure(figsize=(12, 6))

        plt.plot(times_h, cumulative.values, linewidth=1.5)

        plt.xlabel("Simulation time [h]")
        plt.ylabel("Cumulative battery energy [kWh]")
        plt.title("Cumulative state of charge of all buses over the day")

        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def calculate_trip_end_soc(self):
        """
        Calculate SoC statistics at the end of each trip and at each
        vehicle's last depot entry.

        'Ende der Fahrt' is defined as the moment a bus arrives at a
        charging station (chargingStationId switches from NULL/another
        station to a new station id). 'Letzte Einfahrt ins Depot' is
        each vehicle's last such arrival at a depot station.

        Returns
        -------
        dict with:
            'trip_end_soc': {'min', 'mean', 'max'} over all trip-end
                arrivals (at any charging station).
            'last_depot_entry_soc': pandas.Series of SoC per vehicle
                at its last depot arrival.
        """

        df = self.battery_data

        if df.empty:
            print("No battery data available.")
            return {}

        df = df.sort_values(['vehicle', 'time_sec']).copy()
        df['prev_station'] = df.groupby('vehicle')['charging_station_id'].shift(1)
        is_first = df.groupby('vehicle').cumcount() == 0

        # Arrival events: vehicle newly occupies a charging station
        arrivals = df[
            df['charging_station_id'].notna()
            & (df['charging_station_id'] != df['prev_station'])
            & (~is_first)
        ]

        trip_end_soc = arrivals['soc']

        trip_end_stats = {
            'min': trip_end_soc.min(),
            'mean': trip_end_soc.mean(),
            'max': trip_end_soc.max(),
        }

        depot_arrivals = arrivals[arrivals['charging_station_id'].isin(self.DEPOT_STATIONS)]

        last_depot_entry = (
            depot_arrivals
            .sort_values('time_sec')
            .groupby('vehicle')
            .tail(1)
            .set_index('vehicle')['soc']
        )

        print("SoC bei Beendigung der Fahrt (Ankunft an Ladestation):")
        print(f"  Niedrigster SoC: {trip_end_stats['min']:.1f} %")
        print(f"  Durchschnittlicher SoC: {trip_end_stats['mean']:.1f} %")
        print(f"  Höchster SoC: {trip_end_stats['max']:.1f} %")

        print("\nSoC bei letzter Einfahrt ins Depot je Fahrzeug:")
        for vehicle, soc in last_depot_entry.items():
            print(f"  {vehicle}: {soc:.1f} %")

        if not last_depot_entry.empty:
            print(
                f"\n  Niedrigster: {last_depot_entry.min():.1f} % | "
                f"Durchschnitt: {last_depot_entry.mean():.1f} % | "
                f"Höchster: {last_depot_entry.max():.1f} %"
            )

        return {
            'trip_end_soc': trip_end_stats,
            'last_depot_entry_soc': last_depot_entry,
        }

    

if __name__ == "__main__":

    battery_path_II = (
        r"best-ebus\scenario\sumo\output"
        r"\80percent_soc_electric_bus_2026-08-18-12-41-20_battery_aggregated.xml"
    )

    tripinfo_path_II = (
        r"best-ebus\scenario\sumo\output"
        r"\80percent_soc_electric_bus_2026-08-18-12-41-20_tripinfo.xml"
    )

    soc_II = VehicleSOC(battery_path_II)
    soc_II.plot_cumulative_soc()
    soc_II.calculate_trip_end_soc()
    soc_II.plot_soc_over_time(tripinfo_path_II)
