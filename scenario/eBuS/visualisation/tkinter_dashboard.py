"""
Tkinter + Matplotlib Dashboard Template
----------------------------------------
A reusable dashboard shell. Each "panel" is just a Matplotlib Figure
embedded in a Tkinter frame via FigureCanvasTkAgg. To add your own
graph, write a function that takes an Axes object and plots on it,
then register it with `dashboard.add_panel(...)`.

Data comes from a shared DuckDB database (see db.py) instead of CSV
files, so multiple simulation runs can coexist and be switched
between with the "Run" dropdown at the top of the window - run
charging_pv_analysis.py once per simulation to add a run to the DB.

Run:  python dashboard.py
"""

import tkinter as tk
from tkinter import ttk
from functools import partial
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import pandas as pd

from database.db_connector import get_connection, list_runs

# Absolute path to the shared DuckDB database written by
# ChargingPVAnalysis.save_to_db() (run charging_pv_analysis.py
# separately to add/update a run).
# Match this to wherever DBeBuS._load_output()/_load_pv() actually wrote
# ebus.db on this machine (it was created as a relative path,
# "best-ebus/scenario/eBuS/database/ebus.db", from wherever that script
# was run from) - update to the real absolute path if needed.
DB_PATH = r"C:\Users\Ralop\Documents\FU Berlin\BeST-eBuS\best-ebus\scenario\eBuS\database\ebus.db"


def load_run_data(conn, run_id: str) -> dict:
    """
    Pull everything one run needs for the dashboard out of the DB.

    step_time / timestep_time come out of the parquet import as VARCHAR
    (with some blank -> NaN values), so every query casts them to
    DOUBLE with TRY_CAST, which turns unparseable/blank strings into
    NULL instead of erroring.

    solar_power_v6 is wide (one column per second-of-day, e.g. "3600",
    "7200", ...) and has no simulation_timestamp of its own - it's
    unpivoted into the same (station_id, step_time, pv_power) long
    shape the rest of the dashboard expects, and isn't filtered by run
    since it looks like one shared solar profile reused everywhere.

    NOTE: the old battery_results table (station_id, step_time, change,
    ess_absolute) - used by the "Charging Station Detail" panel - has
    no equivalent yet in ebus.db (it came from charging_pv_analysis.py,
    which we're not porting right now). `results` is returned empty
    and that panel is disabled below in App.load_run().
    """
    cs_data = conn.execute(
        """
        SELECT
            TRY_CAST(step_time AS DOUBLE) AS step_time,
            chargingStation_id,
            step_energyCharged
        FROM chargingstations
        WHERE simulation_timestamp = ?
        """,
        [run_id],
    ).df()

    pv_data = conn.execute(
        """
        SELECT
            station_id,
            TRY_CAST(step_time AS DOUBLE) AS step_time,
            pv_power
        FROM (
            UNPIVOT solar_power_v6
            ON COLUMNS(* EXCLUDE (station_id))
            INTO NAME step_time VALUE pv_power
        )
        """
    ).df()

    bt_data = conn.execute(
        """
        SELECT
            vehicle_id,
            TRY_CAST(timestep_time AS DOUBLE) AS timestep_time,
            vehicle_totalEnergyConsumed
        FROM battery
        WHERE simulation_timestamp = ?
        """,
        [run_id],
    ).df()

    results = {}  # station-ESS data not available yet, see docstring above

    return {"cs_data": cs_data, "pv_data": pv_data, "bt_data": bt_data, "results": results}


class Panel(ttk.Frame):
    """A single chart panel: title + matplotlib canvas (+ optional toolbar)."""

    def __init__(self, parent, title, plot_func, figsize=(5, 3.5), dpi=100,
                 show_toolbar=False):
        super().__init__(parent, relief="groove", borderwidth=1)
        self.plot_func = plot_func

        if title:
            ttk.Label(self, text=title, font=("Segoe UI", 11, "bold")).pack(
                anchor="w", padx=6, pady=(4, 0)
            )

        self.fig = Figure(figsize=figsize, dpi=dpi)
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

        if show_toolbar:
            toolbar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
            toolbar.update()
            toolbar.pack(fill="x")

        self.refresh()

    def refresh(self):
        """Clear and redraw this panel's plot."""
        self.ax.clear()
        # Some plot_funcs (e.g. plot_total_hourly_energy) create a
        # twinx() axis each call. Without removing leftover ones here,
        # every refresh piles another axis onto the figure - each
        # refresh click would make the figure progressively heavier
        # and slower to render.
        for extra_ax in list(self.fig.axes):
            if extra_ax is not self.ax:
                self.fig.delaxes(extra_ax)
        self.plot_func(self.ax)
        self.fig.tight_layout()
        self.canvas.draw()


class StationPanel(ttk.Frame):
    """
    Like Panel, but with a dropdown above the chart to pick which
    charging station to display. plot_func here takes (ax, station_id)
    instead of just (ax) - bind any other extra data (e.g. the results
    dict) with functools.partial, same as with a regular Panel.
    """

    def __init__(self, parent, title, plot_func, station_ids,
                 figsize=(5, 3.5), dpi=100):
        super().__init__(parent, relief="groove", borderwidth=1)
        self.plot_func = plot_func
        self.station_ids = list(station_ids)

        header = ttk.Frame(self)
        header.pack(fill="x", padx=6, pady=(4, 0))
        if title:
            ttk.Label(header, text=title, font=("Segoe UI", 11, "bold")).pack(side="left")

        self.station_var = tk.StringVar(
            value=self.station_ids[0] if self.station_ids else ""
        )
        combo = ttk.Combobox(
            header,
            textvariable=self.station_var,
            values=self.station_ids,
            state="readonly",
            width=22,
        )
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh())

        self.fig = Figure(figsize=figsize, dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

        self.refresh()

    def refresh(self):
        """Clear (including any twin axes from the previous draw) and redraw."""
        self.ax.clear()
        for extra_ax in list(self.fig.axes):
            if extra_ax is not self.ax:
                self.fig.delaxes(extra_ax)

        if self.station_ids:
            self.plot_func(self.ax, self.station_var.get())
        else:
            self.ax.set_title("No stations available")

        self.fig.tight_layout()
        self.canvas.draw()


class Dashboard(ttk.Frame):
    """Grid container that manages multiple Panels."""

    def __init__(self, parent, columns=2):
        super().__init__(parent)
        self.columns = columns
        self.panels = []
        self.pack(fill="both", expand=True)

        for i in range(columns):
            self.columnconfigure(i, weight=1)

    def _place(self, panel):
        row = len(self.panels) // self.columns
        col = len(self.panels) % self.columns
        self.rowconfigure(row, weight=1)
        panel.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        self.panels.append(panel)
        return panel

    def add_panel(self, title, plot_func, **panel_kwargs):
        """
        Add a new chart panel.

        title:       string shown above the chart (or "" for none)
        plot_func:   function(ax) -> None, draws on the given Axes
                     (bind any extra data with functools.partial before
                     passing it in here)
        panel_kwargs: passed to Panel (figsize, dpi, show_toolbar, ...)
        """
        return self._place(Panel(self, title, plot_func, **panel_kwargs))

    def add_station_panel(self, title, plot_func, station_ids, **panel_kwargs):
        """
        Add a chart panel with a station-select dropdown.

        title:        string shown above the chart
        plot_func:    function(ax, station_id) -> None
        station_ids:  iterable of selectable station ids for the dropdown
        panel_kwargs: passed to StationPanel (figsize, dpi, ...)
        """
        return self._place(StationPanel(self, title, plot_func, station_ids, **panel_kwargs))

    def refresh_all(self):
        for p in self.panels:
            p.refresh()


# ---------------------------------------------------------------------
# EXAMPLE PLOT FUNCTIONS — replace these with your own logic.
# Each takes a matplotlib Axes (plus any bound extra args) and draws
# on it. Nothing else required.
# ---------------------------------------------------------------------

def plot_total_hourly_energy(ax, station_df: pd.DataFrame, pv_df: pd.DataFrame):
    """
    Plot total charged energy (kWh) and total PV generation (kWh)
    across all charging stations, per hour, for one run.

    station_df: step_time, chargingStation_id, step_energyCharged (Wh)
    pv_df:      station_id, step_time, pv_power (kW, hourly average -
                numerically equal to kWh generated that hour, since
                each row already represents exactly one hour bucket -
                no /1000 or /10 fudge factor needed here).
    """
    if station_df.empty and pv_df.empty:
        ax.set_title("No data for this run")
        return

    station_df = station_df.copy()
    pv_df = pv_df.copy()

    station_df["step_time"] = pd.to_numeric(station_df["step_time"], errors="coerce")
    pv_df["step_time"] = pd.to_numeric(pv_df["step_time"], errors="coerce")

    station_df = station_df[np.isfinite(station_df["step_time"])]
    pv_df = pv_df[np.isfinite(pv_df["step_time"])]

    if station_df.empty and pv_df.empty:
        ax.set_title("No valid data for this run")
        return

    station_df["hour"] = (station_df["step_time"] // 3600).astype(int)

    hourly_charged = station_df.groupby("hour")["step_energyCharged"].sum() / 1000  # Wh -> kWh

    hourly_pv = pv_df.groupby("step_time")["pv_power"].sum()  # already kWh per hour bucket
    hourly_pv.index = hourly_pv.index // 3600

    charged_color = "#3b82f6"
    pv_color = "#f59e0b"

    ax.plot(hourly_charged.index, hourly_charged.values, color=charged_color, linewidth=2)
    ax.set_xlabel("Hour")
    ax.set_ylabel("Charged energy (kWh)", color=charged_color)
    ax.tick_params(axis="y", labelcolor=charged_color)

    ax2 = ax.twinx()
    ax2.plot(hourly_pv.index, hourly_pv.values, color=pv_color, linewidth=2)
    ax2.set_ylabel("Generated PV energy (kWh)", color=pv_color)
    ax2.tick_params(axis="y", labelcolor=pv_color)

    ax.set_title("Total charged energy & PV generation per hour (all stations)")
    ax.grid(True, alpha=0.3)


def plot_charging_stations(ax, station_id, results):
    """
    Plot 'change' (net energy gain/loss per step, in Wh) and
    'ess_absolute' (running battery level, in Wh) over time, for a
    single charging station.

    results: {station_id: [(step_time, change, ess_absolute), ...]}
    for the currently selected run.

    change and ess_absolute live on very different scales (a few Wh of
    net change per step vs. up to hundreds of thousands of Wh of
    battery level), so change goes on the left axis and ess_absolute
    gets its own axis via twinx() on the right, each with matching
    tick-label colors so it's clear which line belongs to which axis.
    """
    rows = results.get(station_id, [])
    if not rows:
        ax.set_title(f"No data for {station_id}")
        return

    step_times, changes, ess_values = zip(*rows)
    hours = [t / 3600 for t in step_times]

    change_color = "#3b82f6"
    ess_color = "#16a34a"

    ax.plot(hours, changes, color=change_color, linewidth=1.5, label="Change")
    ax.axhline(0, color="#94a3b8", linewidth=0.8)
    ax.set_xlabel("Hour")
    ax.set_ylabel("Change (Wh)", color=change_color)
    ax.tick_params(axis="y", labelcolor=change_color)

    ax2 = ax.twinx()
    ax2.plot(hours, ess_values, color=ess_color, linewidth=2, label="Battery level")
    ax2.set_ylabel("Battery level (Wh)", color=ess_color)
    ax2.tick_params(axis="y", labelcolor=ess_color)

    ax.set_title(f"Change & battery level — {station_id}")
    ax.grid(True, alpha=0.3)


def plot_top_total_energy(ax, battery_df):
    """Plot the cumulative energy consumption for the top 20 vehicles."""
    if battery_df is None or battery_df.empty:
        ax.set_title("Top Energy Consumers")
        ax.text(0.5, 0.5, "No battery data for this run", ha="center", va="center")
        return

    required_columns = {"vehicle_id", "timestep_time", "vehicle_totalEnergyConsumed"}
    missing_columns = required_columns.difference(battery_df.columns)
    if missing_columns:
        ax.set_title("Top Energy Consumers")
        ax.text(
            0.5,
            0.5,
            f"Missing columns: {sorted(missing_columns)}",
            ha="center",
            va="center",
        )
        return

    battery_df = battery_df.sort_values(["vehicle_id", "timestep_time"]).copy()

    top20_ids = (
        battery_df.groupby("vehicle_id")["vehicle_totalEnergyConsumed"]
        .max()
        .nlargest(20)
        .index
    )
    top20_df = battery_df[battery_df["vehicle_id"].isin(top20_ids)]

    for vehicle_id, group in top20_df.groupby("vehicle_id"):
        ax.plot(
            group["timestep_time"],
            group["vehicle_totalEnergyConsumed"],
            linewidth=2,
            label=f"Vehicle {vehicle_id}",
        )

    ax.set_title("Top Energy Consumers")
    ax.set_xlabel("Time")
    ax.set_ylabel("Total energy consumed")
    ax.grid(True, alpha=0.3)
    if len(top20_ids) > 0:
        ax.legend(loc="best", fontsize="small")


def plot_scatter(ax):
    x = np.random.randn(100)
    y = np.random.randn(100)
    ax.scatter(x, y, alpha=0.6, color="#f59e0b")
    ax.set_title("Scatter")


def plot_histogram(ax):
    data = np.random.normal(0, 1, 500)
    ax.hist(data, bins=25, color="#ef4444")
    ax.set_title("Histogram")


# ---------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self, db_path: Path):
        super().__init__()
        self.title("SUMO BeST-eBuS Dashboard")
        self.geometry("1600x1200")

        self.conn = get_connection(db_path)
        self.run_ids = list_runs(self.conn)
        if not self.run_ids:
            raise RuntimeError(
                f"No runs found in {db_path} - run charging_pv_analysis.py "
                "at least once first to populate the database."
            )

        header = ttk.Frame(self)
        header.pack(fill="x", padx=8, pady=8)
        ttk.Label(header, text="Dashboard", font=("Segoe UI", 16, "bold")).pack(side="left")

        ttk.Label(header, text="Run:").pack(side="left", padx=(20, 4))
        self.run_var = tk.StringVar(value=self.run_ids[0])
        run_combo = ttk.Combobox(
            header,
            textvariable=self.run_var,
            values=self.run_ids,
            state="readonly",
            width=28,
        )
        run_combo.pack(side="left")
        run_combo.bind("<<ComboboxSelected>>", lambda _e: self.load_run(self.run_var.get()))

        ttk.Button(header, text="Refresh All", command=self.refresh_all).pack(side="right")

        # Scrollable canvas wrapper (in case you add many panels)
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)

        self.dashboard = None
        self.load_run(self.run_ids[0])

    def load_run(self, run_id: str):
        """
        Pull this run's data out of the DB and (re)build every panel
        from scratch. Panels bind their data via functools.partial at
        creation time, so rather than trying to mutate already-bound
        data in place when the run changes, the simplest correct fix
        is to tear down the old panel grid and build a fresh one.
        """
        data = load_run_data(self.conn, run_id)
        self.cs_data = data["cs_data"]
        self.pv_data = data["pv_data"]
        self.bt_data = data["bt_data"]
        self.results = data["results"]

        if self.dashboard is not None:
            self.dashboard.destroy()

        self.dashboard = Dashboard(self.container, columns=2)

        # ---- Register your panels here ----
        # Any plot function that needs extra data beyond `ax` must have
        # that data bound with functools.partial first, since Panel.refresh
        # only ever calls plot_func(ax).
        self.dashboard.add_panel(
            "Total Energy Charged into Buses",
            partial(plot_total_hourly_energy, station_df=self.cs_data, pv_df=self.pv_data),
        )
        # Disabled for now: self.results is empty until the station-ESS
        # (change/ess_absolute) data has a home in ebus.db. Re-enable
        # once that's ported:
        #
        # self.dashboard.add_station_panel(
        #     "Charging Station Detail",
        #     partial(plot_charging_stations, results=self.results),
        #     station_ids=sorted(self.results.keys()) or [""],
        # )
        self.dashboard.add_panel(
            "Top Energy Consumers",
            partial(plot_top_total_energy, battery_df=self.bt_data),
        )
        # To add another: self.dashboard.add_panel("Title", your_plot_func)

    def refresh_all(self):
        self.dashboard.refresh_all()


if __name__ == "__main__":
    app = App(DB_PATH)
    app.mainloop()