# AI generated on 2026-08-18
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from lxml import etree


class ESSPV:

    def __init__(self, ess_path, stations_path=None, pv_csv_path=None):

        self.ess_data = self.parse_ess(ess_path)
        self.station_names = self.parse_station_names(stations_path)
        self.raw_pv_data = self.parse_raw_pv_data(pv_csv_path) if pv_csv_path is not None else None

    def parse_station_names(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        names = {}

        for elem in root.iter('chargingStation'):
            station_id = elem.get('id')
            name = elem.get('name')
            if station_id is None or name is None:
                continue
            names[station_id] = name.replace('_charger', '')

        return names

    def parse_ess(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()

        records = []

        for timestep in root.iter('timestep'):
            time_sec = float(timestep.get('time'))

            for station in timestep.iter('station'):
                records.append({
                    'station_id': station.get('id'),
                    'timestep_min': time_sec / 60,
                    'capacity': float(station.get('capacity')),
                    'pv_generated': float(station.get('pvGenerated')),
                    'energy_charged': float(station.get('energyCharged')),
                    'ess_soc': float(station.get('essSoc')),
                    'grid_energy_drawn': float(station.get('gridEnergyDrawn')),
                    'grid_power_kw': float(station.get('gridPowerKw')),
                    'pv_curtailed': float(station.get('pvCurtailed')),
                })

        df = pd.DataFrame.from_records(records)
        df.sort_values(['station_id', 'timestep_min'], inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

    def parse_raw_pv_data(self, csv_path):
        """
        Read the raw PV input CSV for the run's date (a
        "<start_date>_solar_power_v6_scaled.csv" file produced by
        pv_estimation.pvgis_api_v6 and consumed by EnergyStorageSystem
        as pv_csv_path) and return a DataFrame of hourly PV power [kW],
        indexed by time [h], with one column per station_id.
        """
        df = pd.read_csv(csv_path)
        df['station_id'] = df['station_id'].astype(str)
        df = df.set_index('station_id')
        df = df.drop(columns=['peak_power'])
        df = df[sorted(df.columns, key=lambda c: int(c))]
        df.columns = [int(c) / 3600 for c in df.columns]
        return df.T



    def plot_ess_soc(self, save_path=None):
        """
        Plot ESS state of charge over the course of the day, with one
        line per charging station.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        if self.ess_data.empty:
            print("No ESS data available.")
            return

        stations = sorted(self.ess_data['station_id'].unique())
        colors = plt.cm.tab10.colors

        plt.figure(figsize=(12, 6))

        for i, station in enumerate(stations):
            sdf = self.ess_data[self.ess_data['station_id'] == station].sort_values('timestep_min')
            soc_pct = sdf['ess_soc'] / sdf['capacity'] * 100
            plt.plot(sdf['timestep_min'] / 60, soc_pct, color=colors[i % len(colors)], linewidth=1.2)

        plt.xlabel("Simulation time [h]")
        plt.ylabel("ESS SoC [%]")
        plt.ylim(0, 100)
        plt.title("Battery state of charge per charging station")

        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def plot_pv_vs_charged(self, save_path=None):
        """
        Plot PV generated (solid) against energy charged (dashed) per
        charging station.

        PV generation values are scaled by 1000 to match the source
        data convention.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        if self.ess_data.empty:
            print("No ESS data available.")
            return

        stations = sorted(
            s for s in self.ess_data['station_id'].unique()
            if not s.lower().startswith('cd_')
        )
        colors = plt.cm.tab10.colors

        plt.figure(figsize=(12, 6))

        for i, station in enumerate(stations):
            sdf = self.ess_data[self.ess_data['station_id'] == station].sort_values('timestep_min')
            color = colors[i % len(colors)]
            plt.plot(sdf['timestep_min'] / 60, sdf['pv_generated'] * 1000, color=color, linestyle='-')
            plt.plot(sdf['timestep_min'] / 60, sdf['energy_charged'], color=color, linestyle='--')

        plt.xlabel("Simulation time [h]")
        plt.ylabel("Power [Wh/min]")
        plt.title("PV generated (solid) vs energy charged (dashed) per station")

        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def plot_grid_and_curtailment(self, save_path=None):
        """
        Plot system-wide grid energy drawn and curtailed PV, summed
        across all charging stations.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        if self.ess_data.empty:
            print("No ESS data available.")
            return

        totals = self.ess_data.groupby('timestep_min')[['grid_energy_drawn', 'pv_curtailed']].sum().reset_index()
        hours = totals['timestep_min'] / 60

        plt.figure(figsize=(12, 6))

        plt.fill_between(
            hours, totals['grid_energy_drawn'], step="mid",
            color="tab:red", alpha=0.6, label="Total grid energy drawn [Wh/min]"
        )
        plt.fill_between(
            hours, totals['pv_curtailed'], step="mid",
            color="tab:purple", alpha=0.6, label="Total PV curtailed [Wh/min]"
        )

        plt.xlabel("Simulation time [h]")
        plt.ylabel("Energy [Wh/min]")
        plt.title("System-wide grid dependency and curtailment")

        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=8)
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()


    def plot_grid_power_by_station(self, mark_peaks=True, save_path=None, top_n=10):
        """
        Plot grid power drawn (kW) over time, with one line per charging
        station, using the gridPowerKw values computed by EnergyStorageSystem.

        Parameters
        ----------
        mark_peaks : bool, optional
            If True (default), mark and annotate each station's peak.
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        top_n : int, optional
            If given, only the `top_n` stations with the highest peak grid
            power draw are plotted (default 10). Pass None to plot all
            stations.
        """

        if self.ess_data.empty:
            print("No ESS data available.")
            return

        station_peaks = self.ess_data.groupby('station_id')['grid_power_kw'].max()
        if top_n is not None:
            station_peaks = station_peaks.nlargest(top_n)
        stations = station_peaks.sort_values(ascending=False).index.tolist()
        colors = plt.cm.tab10.colors

        plt.figure(figsize=(12, 6))

        for i, station in enumerate(stations):
            sdf = self.ess_data[self.ess_data['station_id'] == station].sort_values('timestep_min')
            color = colors[i % len(colors)]
            hours = sdf['timestep_min'] / 60
            power_kw = sdf['grid_power_kw']

            station_name = self.station_names.get(station, station)
            plt.plot(hours, power_kw, color=color, label=f"Station {station_name}")

            if mark_peaks:
                peak_idx = power_kw.idxmax()
                peak_hour = hours[peak_idx]
                peak_kw = power_kw[peak_idx]
                plt.scatter(peak_hour, peak_kw, color=color, zorder=5)
                plt.annotate(
                    f'{peak_kw:.1f} kW',
                    (peak_hour, peak_kw),
                    textcoords="offset points", xytext=(0, 6),
                    fontsize=8, color=color,
                )

        plt.xlabel("Simulation time [h]")
        plt.ylabel("Grid power drawn [kW]")
        title = "Grid power demand per charging station"
        if top_n is not None:
            title += f" (top {top_n})"
        plt.title(title)

        plt.grid(True, alpha=0.3)
        plt.legend(loc="upper right", fontsize="small")
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def plot_pv_power(self, save_path=None):
        """
        Plot PV power generation over time, with one line per charging
        station, excluding depots.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        if self.ess_data.empty:
            print("No ESS data available.")
            return

        stations = sorted(
            s for s in self.ess_data['station_id'].unique()
            if not s.lower().startswith('cd_')
        )

        plt.figure(figsize=(12, 6))

        for station in stations:
            sdf = self.ess_data[self.ess_data['station_id'] == station].sort_values('timestep_min')
            hours = sdf['timestep_min'] / 60
            pv_power_kw = sdf['pv_generated'] * 60 / 1000

            plt.plot(hours, pv_power_kw, color="tab:orange", alpha=0.4, linewidth=0.6)

        plt.xlabel("Simulation time [h]")
        plt.ylabel("PV power [kW]")
        plt.title("PV power generation per charging station")

        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def plot_pv_power_per_station(self, save_path=None):
        """
        Plot the normalized PV generation curve (power / peak power) over
        time, with one thin line per charging station, excluding depots.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        if self.ess_data.empty:
            print("No ESS data available.")
            return

        stations = sorted(
            s for s in self.ess_data['station_id'].unique()
            if not s.lower().startswith('cd_')
        )
        colors = plt.cm.tab10.colors

        plt.figure(figsize=(12, 6))

        for i, station in enumerate(stations):
            sdf = self.ess_data[self.ess_data['station_id'] == station].sort_values('timestep_min')
            hours = sdf['timestep_min'] / 60
            pv_power = sdf['pv_generated']
            peak = pv_power.max()
            if peak <= 0:
                continue
            normalized = pv_power / peak

            color = colors[i % len(colors)]
            plt.plot(hours, normalized, color=color, linewidth=0.6)

        plt.xlabel("Simulation time [h]")
        plt.ylabel("Normalized PV power [-]")
        plt.ylim(0, 1.05)
        plt.title("PV generation curve per charging station (normalized to peak)")

        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def plot_raw_pv_data(self, save_path=None):
        """
        Plot the raw, hourly PV input data for the run's date (before any
        per-minute interpolation, pv_factor scaling, or curtailment done
        by EnergyStorageSystem), with one line per charging station
        included in this run.

        Requires pv_csv_path to have been passed to the constructor.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        if self.raw_pv_data is None:
            print("No raw PV data available (pv_csv_path was not provided).")
            return

        included_stations = sorted(
            s for s in self.ess_data['station_id'].unique()
            if not s.lower().startswith('cd_') and s in self.raw_pv_data.columns
        )
        if not included_stations:
            print("None of this run's charging stations were found in the raw PV data.")
            return

        colors = plt.cm.tab10.colors

        plt.figure(figsize=(12, 6))

        for i, station in enumerate(included_stations):
            color = colors[i % len(colors)]
            station_name = self.station_names.get(station, station)
            plt.plot(
                self.raw_pv_data.index, self.raw_pv_data[station],
                color=color, marker='o', markersize=3, linewidth=1,
                label=f"Station {station_name}",
            )

        plt.xlabel("Time [h]")
        plt.ylabel("Raw PV power [kW]")
        plt.title("Raw PV input data per charging station")

        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()


if __name__ == "__main__":

    stations_path = r"best-ebus\scenario\sumo\electric\e_stations.add.xml"
    ess_path_II = (
        r"best-ebus\scenario\sumo\output"
        r"\80percent_soc_electric_bus_2026-08-18-18-33-24_ess.xml"
    )
    pv_csv_path = r"best-ebus\scenario\eBuS\pv_estimation\data\2024-02-22_solar_power_v6_scaled.csv"

    ess_pv_II = ESSPV(ess_path_II, stations_path, pv_csv_path)
    ess_pv_II.plot_ess_soc()
    ess_pv_II.plot_pv_vs_charged()
    ess_pv_II.plot_grid_and_curtailment()
    ess_pv_II.plot_raw_pv_data()
