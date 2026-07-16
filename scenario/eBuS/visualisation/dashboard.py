"""
Tkinter + Matplotlib Dashboard Template
----------------------------------------
A reusable dashboard shell. Each "panel" is just a Matplotlib Figure
embedded in a Tkinter frame via FigureCanvasTkAgg. To add your own
graph, write a function that takes an Axes object and plots on it,
then register it with `dashboard.add_panel(...)`.

Run:  python dashboard.py
"""

import tkinter as tk
from tkinter import ttk
from functools import partial
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import pandas as pd


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
        self.plot_func(self.ax)
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

    def add_panel(self, title, plot_func, **panel_kwargs):
        """
        Add a new chart panel.

        title:       string shown above the chart (or "" for none)
        plot_func:   function(ax) -> None, draws on the given Axes
                     (bind any extra data with functools.partial before
                     passing it in here)
        panel_kwargs: passed to Panel (figsize, dpi, show_toolbar, ...)
        """
        row = len(self.panels) // self.columns
        col = len(self.panels) % self.columns
        self.rowconfigure(row, weight=1)

        panel = Panel(self, title, plot_func, **panel_kwargs)
        panel.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        self.panels.append(panel)
        return panel

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
    Plot the total charged energy (kWh) across all charging stations per hour.
    Assumes step_energyCharged is in Wh.
    """
    station_df = station_df.dropna(subset=["step_time"]).copy()

    # Hour since simulation start
    station_df["hour"] = (station_df["step_time"] // 3600).astype(int)

    hourly = (
        station_df.groupby("hour")["step_energyCharged"]
        .sum()
        .reset_index()
    )

    # Convert Wh -> kWh
    hourly["step_energyCharged"] /= 1000

    ax.plot(
        hourly["hour"],
        hourly["step_energyCharged"],
        linewidth=2,
    )

   # Sum over all stations (excluding first row and first column)
    hourly_pf = pv_df.iloc[1:, 1:].sum(axis=0) / 10 # Should be divided by 1000, so 100x energy of current solar setting is requiered

    # Convert column names (3600, 7200, ...) to hour numbers (1, 2, ...)
    pv_hours = hourly_pf.index.astype(int) // 3600

    ax.plot(
        pv_hours,
        hourly_pf.values,
        label="PV Energy",
        linewidth=2,
    )
    ax2 = ax.twinx()
    ax.set_xlabel("Hour")
    ax.set_ylabel("Charged energy (kWh)")
    ax2.set_ylabel("Generated PV Energy kWh")
    ax.set_title("Total charged energy per hour (all stations)")
    ax.grid(True)


def plot_bar(ax):
    categories = ["A", "B", "C", "D"]
    values = np.random.randint(5, 20, size=4)
    ax.bar(categories, values, color="#10b981")
    ax.set_title("Random bars")


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
    def __init__(self, date_of_run):
        super().__init__()
        self.title("SUMO BeST-eBuS Dashboard")
        self.geometry("1600x1200")
        self.cs_data = pd.read_csv(
            f"best-ebus/scenario/sumo/output/electric_bus_{date_of_run}_chargingsstations.csv",
            sep=";",
        )
        self.bt_data = pd.read_csv(
            f"best-ebus/scenario/sumo/output/electric_bus_{date_of_run}_battery.csv",
            sep=";",
        )
        self.pv_data = pd.read_csv("best-ebus/scenario/eBuS/ext_data/solar_power.csv")

        header = ttk.Frame(self)
        header.pack(fill="x", padx=8, pady=8)
        ttk.Label(header, text="Dashboard", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(header, text="Refresh All", command=self.refresh_all).pack(side="right")

        # Scrollable canvas wrapper (in case you add many panels)
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.dashboard = Dashboard(container, columns=2)

        # ---- Register your panels here ----
        # Any plot function that needs extra data beyond `ax` must have
        # that data bound with functools.partial first, since Panel.refresh
        # only ever calls plot_func(ax).
        self.dashboard.add_panel(
            "Total Energy Charged into Buses",
            partial(plot_total_hourly_energy, station_df=self.cs_data, pv_df = self.pv_data),
        )
        self.dashboard.add_panel("Random Bars", plot_bar)
        self.dashboard.add_panel("Scatter Plot", plot_scatter, show_toolbar=True)
        self.dashboard.add_panel("Histogram", plot_histogram)
        # To add another: self.dashboard.add_panel("Title", your_plot_func)

    def refresh_all(self):
        self.dashboard.refresh_all()


if __name__ == "__main__":
    date_of_run: str = "2026-07-16-11-29-38"
    app = App(date_of_run)
    app.mainloop()