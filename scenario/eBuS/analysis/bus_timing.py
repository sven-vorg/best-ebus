# AI generated on 2026-08-18
from pathlib import Path

from lxml import etree
import numpy as np
import matplotlib.pyplot as plt


class BusTiming:

    EXCLUDED_STOPS = {'bs_cicerostrasse', 'bs_muellerstrasse'}

    def __init__(self, stops_path):
        self.stops = self.parse_stops(stops_path)

    def parse_stops(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()

        stops = []

        for elem in root.iter('stopinfo'):
            bus_stop = elem.get('busStop')

            if bus_stop in self.EXCLUDED_STOPS:
                continue

            stops.append({
                'stop_id': elem.get('id'),
                'vehicle': elem.get('type'),
                'bus_stop': bus_stop,
                'lane': elem.get('lane'),
                'pos': float(elem.get('pos')),
                'started_sec': float(elem.get('started')),
                'ended_sec': float(elem.get('ended')),
                'delay_sec': float(elem.get('delay')),
            })

        stops.sort(key=lambda x: x['started_sec'])

        return stops

    def get_delays(self):
        return [stop['delay_sec'] for stop in self.stops]

    def print_stops(self):
        for stop in self.stops:
            print(
                f"Time: {stop['started_sec']:8.2f} sec | "
                f"Stop: {stop['stop_id']:>5} | "
                f"Bus stop: {stop['bus_stop']:<20} | "
                f"Delay: {stop['delay_sec']:6.2f} sec"
            )

    def aggregate_delays(self, interval=60):
        """
        Aggregate delays into fixed time intervals.

        Parameters
        ----------
        interval : int or float
            Length of each interval in seconds.

        Returns
        -------
        interval_times : numpy.ndarray
            Start time of each interval.
        mean_delays : numpy.ndarray
            Mean delay within each interval.
        """

        if not self.stops:
            return np.array([]), np.array([])

        times = np.array(
            [stop['started_sec'] for stop in self.stops]
        )

        delays = np.array(
            [stop['delay_sec'] for stop in self.stops]
        )

        # Start at t = 0 and continue until the end of the simulation
        max_time = times.max()

        bins = np.arange(
            0,
            np.ceil(max_time / interval) * interval + interval,
            interval
        )

        # Determine which interval each stop belongs to
        interval_indices = np.digitize(times, bins) - 1

        # Calculate mean delay for each interval
        mean_delays = []

        for i in range(len(bins) - 1):
            mask = interval_indices == i

            if np.any(mask):
                mean_delays.append(np.mean(delays[mask]))
            else:
                mean_delays.append(np.nan)

        interval_times = bins[:-1]

        return interval_times, np.array(mean_delays)

    def plot_aggregated_delays(self, interval=60, save_path=None):
        """
        Plot mean delay aggregated over fixed time intervals.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        times, delays = self.aggregate_delays(interval)

        if len(times) == 0:
            print("No stop data available.")
            return

        plt.figure(figsize=(12, 6))

        plt.plot(
            times,
            delays,
            marker='o',
            linewidth=1.5,
            markersize=3
        )

        plt.xlabel("Simulation time [s]")
        plt.ylabel("Mean delay [s]")
        plt.title(f"Mean bus delay per {interval}-second interval")

        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def plot_delay_per_bus(self, save_path=None):
        """
        Plot delay over simulation time for every bus.

        Each bus is represented by a separate line.

        Parameters
        ----------
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        if not self.stops:
            print("No stop data available.")
            return

        # Group stops by bus ID
        buses = {}

        for stop in self.stops:
            bus_id = stop['stop_id']

            if bus_id not in buses:
                buses[bus_id] = {
                    'times': [],
                    'delays': []
                }

            buses[bus_id]['times'].append(stop['started_sec'])
            buses[bus_id]['delays'].append(stop['delay_sec'])

        plt.figure(figsize=(12, 6))

        # Plot each bus separately
        for bus_id, data in buses.items():
            plt.plot(
                data['times'],
                data['delays'],
                #marker='o',
                linewidth=1.2,
                markersize=3,
                label=f"Bus {bus_id}"
            )

        plt.xlabel("Simulation time [s]")
        plt.ylabel("Delay [s]")
        plt.title("Bus delay over time")

        plt.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

    def count_active_long_stops(self, interval=60, min_duration=20):
        """
        Count buses currently in a stop longer than `min_duration` seconds,
        for each fixed time interval.

        A stop is counted in every interval it overlaps, not just the one
        it started in, so a bus dwelling across an interval boundary is
        counted as active in both.

        Parameters
        ----------
        interval : int or float
            Length of each interval in seconds.
        min_duration : int or float
            Minimum stop duration (ended - started) to be counted.

        Returns
        -------
        interval_times : numpy.ndarray
            Start time of each interval.
        counts : numpy.ndarray
            Number of distinct buses with an active long stop in each interval.
        """

        long_stops = [
            stop for stop in self.stops
            if (stop['ended_sec'] - stop['started_sec']) > min_duration
        ]

        if not long_stops:
            return np.array([]), np.array([])

        max_time = max(stop['ended_sec'] for stop in long_stops)

        bins = np.arange(
            0,
            np.ceil(max_time / interval) * interval + interval,
            interval
        )

        interval_times = bins[:-1]
        counts = np.zeros(len(interval_times), dtype=int)

        for i, bin_start in enumerate(interval_times):
            bin_end = bin_start + interval

            active_ids = {
                stop['stop_id'] for stop in long_stops
                if stop['started_sec'] < bin_end and stop['ended_sec'] > bin_start
            }

            counts[i] = len(active_ids)

        return interval_times, counts

    def plot_active_long_stops(self, interval=60, min_duration=20, save_path=None):
        """
        Plot the number of buses in a stop longer than `min_duration`
        seconds, per fixed time interval.

        Parameters
        ----------
        interval : int or float
            Length of each interval in seconds.
        min_duration : int or float
            Minimum stop duration (ended - started) to be counted.
        save_path : str or Path, optional
            If given, the figure is saved to this path.
        """

        times, counts = self.count_active_long_stops(interval, min_duration)

        if len(times) == 0:
            print("No stop data available.")
            return

        plt.figure(figsize=(12, 6))

        plt.step(
            times,
            counts,
            where='post',
            linewidth=1.5
        )

        plt.xlabel("Simulation time [s]")
        plt.ylabel(f"Buses in stop > {min_duration}s")
        plt.title(f"Active long stops per {interval}-second interval")

        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()

if __name__ == "__main__":

    stops_path_II = (
        r"best-ebus\scenario\sumo\output"
        r"\80percent_soc_electric_bus_2026-08-18-18-33-24_stopinfo.xml"
    )

    delay_II = BusTiming(stops_path=stops_path_II)
    delay_II.plot_delay_per_bus()