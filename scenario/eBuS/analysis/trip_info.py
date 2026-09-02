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

    def __init__(self, tripinfo_path, chargingstations_path=None):

        self.trip_data = self.parse_tripinfo(tripinfo_path)

        if chargingstations_path is not None:
            energy_charged = self.parse_charging_energy(chargingstations_path)
            self.trip_data['energy_charged'] = (
                self.trip_data['vehicle'].map(energy_charged).fillna(0.0)
            )
        else:
            self.trip_data['energy_charged'] = 0.0

        # Net energy actually supplied for the trip: motor draw, less
        # what regenerative braking recovered, plus whatever was
        # externally charged into the battery along the way.
        self.trip_data['net_energy_consumed'] = (
            self.trip_data['total_energy_consumed']
            - self.trip_data['total_energy_regenerated']
            + self.trip_data['energy_charged']
        )

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
                'total_energy_regenerated': (
                    float(battery.get('totalEnergyRegenerated'))
                    if battery is not None else float('nan')
                ),
            })

        return pd.DataFrame.from_records(records)

    def parse_charging_energy(self, xml_path):
        """
        Sum energy charged into each vehicle across all charging events.

        Returns
        -------
        dict mapping vehicle id to total energy charged (Wh).
        """

        tree = etree.parse(xml_path)
        root = tree.getroot()

        energy_by_vehicle = {}

        for elem in root.iter('chargingEvent'):
            vehicle = elem.get('vehicle')
            energy = float(elem.get('totalEnergyChargedIntoVehicle', 0))
            energy_by_vehicle[vehicle] = energy_by_vehicle.get(vehicle, 0.0) + energy

        return energy_by_vehicle

    def plot_route_length_vs_energy(self, save_path=None):
        """
        Scatter plot with one point per bus: route length vs. net
        energy consumed (consumed minus regenerated, plus any energy
        charged along the route), colored by vehicle type (vType).

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        df = self.trip_data.dropna(subset=['route_length', 'net_energy_consumed'])

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
            y = subset['net_energy_consumed'] / 1000  # Wh -> kWh

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
        plt.ylabel("Net energy consumed [kWh]")
        plt.title("Route length vs. net energy consumed per bus")

        plt.grid(True, alpha=0.3)
        plt.legend(title="Vehicle type")
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def plot_efficiency_boxplot(self, save_path=None):
        """
        Boxplot of per-bus net energy consumption per km (kWh/km),
        grouped by vehicle type. Net energy is consumed minus
        regenerated, plus any energy charged along the route.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        df = self.trip_data.dropna(subset=['route_length', 'net_energy_consumed'])
        df = df[df['route_length'] > 0]

        if df.empty:
            print("No trip data available.")
            return

        efficiency = (
            (df['net_energy_consumed'] / 1000)  # Wh -> kWh
            / (df['route_length'] / 1000)  # m -> km
        )
        df = df.assign(efficiency=efficiency)

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

        data = [df.loc[df['vtype'] == vtype, 'efficiency'] for vtype in vtypes]

        print("Energy consumption per km statistics by vehicle type (kWh/km):")
        for vtype, values in zip(vtypes, data):
            q1, median, q3 = values.quantile([0.25, 0.5, 0.75])
            iqr = q3 - q1
            in_whiskers = values[(values >= q1 - 1.5 * iqr) & (values <= q3 + 1.5 * iqr)]
            whisker_low, whisker_high = in_whiskers.min(), in_whiskers.max()
            n_outliers = len(values) - len(in_whiskers)
            print(
                f"  {vtype}: n={len(values)}, min={values.min():.2f}, "
                f"Q1={q1:.2f}, median={median:.2f}, Q3={q3:.2f}, max={values.max():.2f}, "
                f"IQR={iqr:.2f}, whiskers=[{whisker_low:.2f}, {whisker_high:.2f}], "
                f"outliers={n_outliers}"
            )

        plt.figure(figsize=(8, 6))

        box = plt.boxplot(
            data,
            tick_labels=vtypes,
            patch_artist=True,
            medianprops={'color': 'black'},
        )

        for patch, vtype in zip(box['boxes'], vtypes):
            patch.set_facecolor(color_map[vtype])
            patch.set_alpha(0.7)

        plt.xlabel("Vehicle type")
        plt.ylabel("Energy consumption [kWh/km]")
        plt.title("Energy consumption per km by bus type")

        plt.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def calculate_energy_efficiency(self):
        """
        Calculate average energy efficiency (kWh/km) per vehicle type.

        Per-bus efficiency is net energy consumed (total energy
        consumed, minus regenerated, plus any energy charged along the
        route) divided by route length; the per-vType figure is the
        mean of those per-bus values.

        Returns
        -------
        pandas.Series indexed by vType, giving mean kWh/km.
        """

        df = self.trip_data.dropna(subset=['route_length', 'net_energy_consumed'])
        df = df[df['route_length'] > 0]

        if df.empty:
            print("No trip data available.")
            return pd.Series(dtype=float)

        efficiency_kwh_per_km = (
            (df['net_energy_consumed'] / 1000)  # Wh -> kWh
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
    chargingstations_path = (
        r"best-ebus\scenario\sumo\output\run_2026-08-29-00-42-22"
        r"\electric_bus_2026-08-29-00-42-22_chargingstations.xml"
    )

    ti = TripInfo(tripinfo_path, chargingstations_path)
    ti.plot_route_length_vs_energy()
    ti.plot_efficiency_boxplot()
    ti.calculate_energy_efficiency()
