# AI generated on 2026-08-29
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from lxml import etree


class TripInfo:

    # Fixed, colorblind-safe categorical palette, in a validated non-cycling
    # order. Past this many vTypes, extra series would need to fold into
    # "Other" rather than repeat a color.
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

    def __init__(self, tripinfo_path):

        self.trip_data = self.parse_tripinfo(tripinfo_path)

    def parse_tripinfo(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()

        records = []

        for trip in root.iter('tripinfo'):
            battery = trip.find('battery')

            records.append({
                'vehicle': trip.get('id'),
                'vtype': trip.get('vType'),
                'route_length': float(trip.get('routeLength')),
                'total_energy_consumed': (
                    float(battery.get('totalEnergyConsumed'))
                    if battery is not None else float('nan')
                ),
            })

        return pd.DataFrame.from_records(records)

    def plot_route_length_vs_energy(self, save_path=None):
        """
        Scatter plot with one point per bus: route length vs. total
        energy consumed, colored by vehicle type (vType).

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        df = self.trip_data.dropna(subset=['route_length', 'total_energy_consumed'])

        if df.empty:
            print("No trip data available.")
            return

        vtypes = sorted(df['vtype'].dropna().unique())

        if len(vtypes) > len(self.PALETTE):
            print(
                f"Warning: {len(vtypes)} vehicle types exceed the "
                f"{len(self.PALETTE)}-color palette; colors will repeat."
            )

        color_map = {
            vtype: self.PALETTE[i % len(self.PALETTE)]
            for i, vtype in enumerate(vtypes)
        }

        plt.figure(figsize=(10, 7))

        for vtype in vtypes:
            subset = df[df['vtype'] == vtype]
            x = subset['route_length'] / 1000  # m -> km
            y = subset['total_energy_consumed'] / 1000  # Wh -> kWh

            plt.scatter(
                x, y,
                label=vtype,
                color=color_map[vtype],
                s=28,
                alpha=0.8,
                edgecolors='none',
            )

            if len(subset) >= 2:
                slope, intercept = np.polyfit(x, y, 1)
                x_fit = np.array([x.min(), x.max()])
                plt.plot(
                    x_fit, slope * x_fit + intercept,
                    color=color_map[vtype],
                    linestyle='--',
                    linewidth=1.5,
                )

        plt.xlabel("Route length [km]")
        plt.ylabel("Total energy consumed [kWh]")
        plt.title("Route length vs. total energy consumed per bus")

        plt.grid(True, alpha=0.3)
        plt.legend(title="Vehicle type")
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def calculate_energy_efficiency(self):
        """
        Calculate average energy efficiency (kWh/km) per vehicle type.

        Per-bus efficiency is total energy consumed divided by route
        length; the per-vType figure is the mean of those per-bus values.

        Returns
        -------
        pandas.Series indexed by vType, giving mean kWh/km.
        """

        df = self.trip_data.dropna(subset=['route_length', 'total_energy_consumed'])
        df = df[df['route_length'] > 0]

        if df.empty:
            print("No trip data available.")
            return pd.Series(dtype=float)

        efficiency_kwh_per_km = (
            (df['total_energy_consumed'] / 1000)  # Wh -> kWh
            / (df['route_length'] / 1000)  # m -> km
        )

        efficiency_by_vtype = (
            efficiency_kwh_per_km
            .groupby(df['vtype'])
            .mean()
            .sort_index()
        )

        print("Average energy efficiency per vehicle type:")
        for vtype, value in efficiency_by_vtype.items():
            print(f"  {vtype}: {value:.2f} kWh/km")

        return efficiency_by_vtype


if __name__ == "__main__":

    tripinfo_path = (
        r"best-ebus\scenario\sumo\output\run_2026-08-29-00-42-22"
        r"\electric_bus_2026-08-29-00-42-22_tripinfo.xml"
    )

    ti = TripInfo(tripinfo_path)
    ti.plot_route_length_vs_energy()
    ti.calculate_energy_efficiency()
