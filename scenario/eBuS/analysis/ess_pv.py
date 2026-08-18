# AI generated on 2026-08-18
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from lxml import etree


class ESSPV:

    def __init__(self, ess_path):

        self.ess_data = self.parse_ess(ess_path)

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
                    'pv_generated': float(station.get('pvGenerated')),
                    'energy_charged': float(station.get('energyCharged')),
                    'ess_soc': float(station.get('essSoc')),
                    'grid_energy_drawn': float(station.get('gridEnergyDrawn')),
                    'pv_curtailed': float(station.get('pvCurtailed')),
                })

        df = pd.DataFrame.from_records(records)
        df.sort_values(['station_id', 'timestep_min'], inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df

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
            plt.plot(sdf['timestep_min'] / 60, sdf['ess_soc'], color=colors[i % len(colors)], linewidth=1.2)

        plt.xlabel("Simulation time [h]")
        plt.ylabel("ESS SoC [Wh]")
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

        stations = sorted(self.ess_data['station_id'].unique())
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


if __name__ == "__main__":

    ess_path_II = (
        r"best-ebus\scenario\sumo\output"
        r"\80percent_soc_electric_bus_2026-08-18-18-33-24_ess.xml"
    )

    ess_pv_II = ESSPV(ess_path_II)
    ess_pv_II.plot_ess_soc()
    ess_pv_II.plot_pv_vs_charged()
    ess_pv_II.plot_grid_and_curtailment()
