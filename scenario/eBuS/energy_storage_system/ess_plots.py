import pandas as pd
import matplotlib.pyplot as plt


def plot_combined(csv_path="ess_output.csv", save_path="ess_combined_plot.png"):
    """
    Single combined figure comparing all charging stations:
      1. ESS state of charge per station (line per station)
      2. PV generated (solid) vs energy charged (dashed), per station
      3. System-wide grid draw and curtailed PV, summed across all stations

    Expects columns: station_id, timestep_min, pv_generated,
    energy_charged, ess_soc, grid_energy_drawn, pv_curtailed
    """
    df = pd.read_csv(csv_path)
    df = df.round(6)
    
    # Multiply PV generation by 1000
    df["pv_generated"] = df["pv_generated"] * 1000
    df["hour"] = df["timestep_min"] / 60  # nicer x-axis than raw minutes

    stations = sorted(df["station_id"].unique())
    colors = plt.cm.tab10.colors  # 10 distinct colors, cycles if more stations

    fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    fig.suptitle("ESS Simulation — All Stations", fontsize=14)

    # --- Panel 1: ESS SoC per station ---
    ax1 = axes[0]
    for i, station in enumerate(stations):
        sdf = df[df["station_id"] == station].sort_values("timestep_min")
        ax1.plot(sdf["hour"], sdf["ess_soc"], color=colors[i % len(colors)])
    ax1.set_ylabel("ESS SoC (Wh)")
    ax1.set_title("Battery State of Charge")
    ax1.grid(alpha=0.3)

    # --- Panel 2: PV generated (solid) vs energy charged (dashed), per station ---
    ax2 = axes[1]
    for i, station in enumerate(stations):
        sdf = df[df["station_id"] == station].sort_values("timestep_min")
        color = colors[i % len(colors)]
        ax2.plot(sdf["hour"], sdf["pv_generated"], color=color, linestyle="-")
        ax2.plot(sdf["hour"], sdf["energy_charged"], color=color, linestyle="--")
    ax2.set_ylabel("Power (Wh/min)")
    ax2.set_title("PV Generated (solid) vs Energy Charged (dashed)")
    ax2.grid(alpha=0.3)

    # --- Panel 3: system-wide grid draw & curtailed PV, summed across stations ---
    ax3 = axes[2]
    totals = df.groupby("timestep_min")[["grid_energy_drawn", "pv_curtailed"]].sum().reset_index()
    totals["hour"] = totals["timestep_min"] / 60
    ax3.fill_between(totals["hour"], totals["grid_energy_drawn"], step="mid",
                      color="tab:red", alpha=0.6, label="Total grid energy drawn (Wh/min)")
    ax3.fill_between(totals["hour"], totals["pv_curtailed"], step="mid",
                      color="tab:purple", alpha=0.6, label="Total PV curtailed (Wh/min)")
    ax3.set_xlabel("Time (hours)")
    ax3.set_ylabel("Energy (Wh/min)")
    ax3.set_title("System-Wide Grid Dependency & Curtailment")
    ax3.legend(loc="upper right", fontsize=8)
    ax3.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.show()


if __name__ == "__main__":
    plot_combined(
        csv_path = r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\eBuS\files\output\ess_output.csv",
        save_path = r"C:\Users\svens\Documents\FU-Berlin\BeST-eBuS\best-ebus\scenario\eBuS\visualisation\plots\ess_combined_plot.svg")