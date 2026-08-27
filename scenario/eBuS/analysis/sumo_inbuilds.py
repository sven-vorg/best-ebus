# AI generated on 2026-08-20
import logging
import os
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


class SumoInbuilds:
    """Thin wrappers around SUMO's own tools/*.py analysis and plotting scripts."""

    HEARTBEAT_INTERVAL = 10  # seconds between "still running" log messages

    def __init__(self, sumo_home=None):
        self.sumo_home = Path(sumo_home or os.environ["SUMO_HOME"])

    def _tool(self, relative_path):
        return (self.sumo_home / relative_path).resolve()

    def _run(self, args, label):
        logger.info("%s: starting", label)
        start = time.monotonic()

        process = subprocess.Popen(
            [sys.executable, *(str(a) for a in args)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stop_heartbeat = threading.Event()

        def heartbeat():
            while not stop_heartbeat.wait(self.HEARTBEAT_INTERVAL):
                logger.info(
                    "%s: still running (%.0fs elapsed)",
                    label,
                    time.monotonic() - start,
                )

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()

        try:
            stdout, stderr = process.communicate()
        finally:
            stop_heartbeat.set()
            heartbeat_thread.join()

        elapsed = time.monotonic() - start
        result = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)

        if result.returncode != 0:
            logger.error("%s: failed after %.1fs (return code %s)", label, elapsed, result.returncode)
            logger.error("STDERR: %s", result.stderr)
            logger.error("STDOUT: %s", result.stdout)
        else:
            logger.info("%s: finished in %.1fs", label, elapsed)

        return result

    @staticmethod
    def _get_first_route_id(route_path):
        """Return the id of the first route found in a SUMO route file."""
        for _, elem in ET.iterparse(route_path, events=("start",)):
            if elem.tag == "route" and "id" in elem.attrib:
                return elem.attrib["id"]
        raise ValueError(f"No route with an id found in {route_path}")

    def plot_trajectories(self, fcdinfo_path, save_path):
        """
        Scatter plot of all vehicle positions (xy) recorded in an
        fcd-output file.

        Parameters
        ----------
        fcdinfo_path : str or Path
            SUMO fcd-output XML file.
        save_path : str or Path
            Path the resulting plot is written to.
        """

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        self._run([
            self._tool("tools/plot_trajectories.py"),
            "-t", "xy",
            "-o", str(save_path),
            str(fcdinfo_path),
            "--scatterplot",
        ], "plot_trajectories")


    # Broken atm
    def plot_stops(self, route_path, stops_path):
        """
        Plot the scheduled stops of the first route in `route_path`
        against the stop layout in `stops_path`.

        Parameters
        ----------
        route_path : str or Path
            SUMO route file containing at least one <route> with stops.
        stops_path : str or Path
            Additional file defining the bus stops.
        """

        route_id = self._get_first_route_id(route_path)

        self._run([
            self._tool("tools/visualization/plotStops.py"),
            "-r", str(route_path),
            "-a", str(stops_path),
            "-i", route_id,
            "-v",
            "--legend",
            "--filter-ids", "*",
        ], "plotStops")

    def compute_stopping_place_usage(self, stopinfo_path):
        """
        Print stopping-place usage statistics computed from a
        stopinfo-output file.

        Parameters
        ----------
        stopinfo_path : str or Path
            SUMO stopinfo-output XML file.
        """

        self._run([
            self._tool("tools/output/computeStoppingPlaceUsage.py"),
            "-s", str(stopinfo_path),
        ], "computeStoppingPlaceUsage")

    def trip_statistics(self, tripinfo_path, save_path):
        """
        Write aggregated trip statistics to a text file.

        Parameters
        ----------
        tripinfo_path : str or Path
            SUMO tripinfo-output XML file.
        save_path : str or Path
            Path the statistics text file is written to.
        """

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        self._run([
            self._tool("tools/output/tripStatistics.py"),
            "-t", str(tripinfo_path),
            "-o", str(save_path),
            "-e",
        ], "tripStatistics")

    def plot_battery_energy(self, battery_aggregated_path, save_path):
        """
        Plot energy consumed per bus over time from an aggregated
        battery-output file.

        Parameters
        ----------
        battery_aggregated_path : str or Path
            SUMO battery-output XML file (aggregated).
        save_path : str or Path
            Path the resulting plot is written to.
        """

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        self._run([
            self._tool("tools/visualization/plotXMLAttributes.py"),
            "-x", "time",
            "-y", "energyConsumed",
            "--idattr", "id",
            "--xlabel", "time [s]",
            "--ylabel", "energy [Wh]",
            "--title", "Energy consumed per bus over time",
            "-o", str(save_path),
            str(battery_aggregated_path),
        ], "plotXMLAttributes (battery energy)")

    def plot_charging_events_scatter(self, chargingstations_path, save_path):
        """
        Scatter plot of charging events (energy charged into the
        vehicle vs. charging start time) from a chargingstations-output
        file.

        Parameters
        ----------
        chargingstations_path : str or Path
            SUMO chargingstations-output XML file.
        save_path : str or Path
            Path the resulting plot is written to.
        """

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        self._run([
            self._tool("tools/visualization/plotXMLAttributes.py"),
            "-x", "chargingBegin",
            "-y", "totalEnergyChargedIntoVehicle",
            "--idattr", "chargingStationId",
            "--xlabel", "time [s]",
            "--ylabel", "energy [Wh]",
            "--title", "Charging events over time",
            "-o", str(save_path),
            str(chargingstations_path),
            "--scatterplot",
        ], "plotXMLAttributes (charging events)")
