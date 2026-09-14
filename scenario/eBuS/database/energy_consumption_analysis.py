import os

import duckdb
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2", "#937860"]

STATION_NAMES = {
    "cs_agg_12472_23_9836_31_9897_34_11923_50_11973_33_12043_1_9852_20": "Wilhelmsruher Damm (Berlin)",
    "cs_agg_9897_0_9973_34_9889_51_9963_0": "Berlin, Alt-Heiligensee",
}


class EnergyConsumptionAnalysis:

    def _styled_boxplot(data, labels, xlabel, ylabel):
        fig, ax = plt.subplots(figsize=(10, 7))

        bp = ax.boxplot(
            data,
            tick_labels=labels,
            patch_artist=True,
            widths=0.5,
            medianprops={"color": "black"},
            whiskerprops={"color": "black"},
            capprops={"color": "black"},
            flierprops={"marker": "o", "markerfacecolor": "none", "markeredgecolor": "black", "markersize": 6},
            boxprops={"edgecolor": "black"},
        )

        for patch, color in zip(bp["boxes"], PALETTE):
            patch.set_facecolor(color)

        ax.set_axisbelow(True)
        ax.yaxis.grid(True, color="0.85", linewidth=0.8)
        ax.xaxis.grid(False)
        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")

        for spine in ax.spines.values():
            spine.set_color("black")
            spine.set_linewidth(0.8)

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="both", colors="black")

        fig.tight_layout()
        return fig, ax

    def total_energy_consumption():
        con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")

        df = con.execute("""
            SELECT scenario, seed, sum(battery_totalEnergyConsumed) AS battery_totalEnergyConsumed
            FROM multirun_tripinfo
            GROUP BY scenario, seed
            ORDER BY scenario, seed
        """).fetchdf()
        print(df.dtypes)

        con.close()
        df["battery_totalEnergyConsumed"] = df["battery_totalEnergyConsumed"] / 1_000_000
        print(df.head())

        scenarios = ["summer", "winter", "reduced"]
        data = [df[df["scenario"] == scenario]["battery_totalEnergyConsumed"] for scenario in scenarios]
        EnergyConsumptionAnalysis._styled_boxplot(
            data, scenarios, xlabel="Scenario", ylabel="Energy consumption [MWh]"
        )
        plt.show()

        for scenario in scenarios:
            subset = df[df["scenario"] == scenario]
            print(scenario)
            print(subset.describe())
            EnergyConsumptionAnalysis._styled_boxplot(
                [subset["battery_totalEnergyConsumed"]],
                [scenario],
                xlabel="Scenario",
                ylabel="Energy consumption [MWh]",
            )
            plt.show()

    def energy_consumption_by_type():
        con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")

        df = con.execute("""
            SELECT
                battery_totalEnergyConsumed,
                tripinfo_vType,
                scenario
            FROM multirun_tripinfo
        """).fetchdf()

        con.close()

        df["battery_totalEnergyConsumed"] = df["battery_totalEnergyConsumed"] / 1_000

        for scenario in ["summer", "winter", "reduced"]:
            subset = df[df["scenario"] == scenario]
            vtypes = sorted(subset["tripinfo_vType"].unique())
            data = [subset[subset["tripinfo_vType"] == vtype]["battery_totalEnergyConsumed"] for vtype in vtypes]
            EnergyConsumptionAnalysis._styled_boxplot(
                data, vtypes, xlabel="Vehicle type", ylabel="Energy consumption [kWh]"
            )
            plt.show()

    def energy_over_distance_scatter(output_dir=r"C:\Users\Ralop\Nextcloud\Masterarbeit\Grafiken\Plots"):
        con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")
        df = con.execute("""
            SELECT
                battery_totalEnergyConsumed,
                tripinfo_routeLength,
                tripinfo_vType,
                scenario
            FROM multirun_tripinfo
        """).fetchdf()
        con.close()
        df["battery_totalEnergyConsumed"] = df["battery_totalEnergyConsumed"] / 1_000
        df["tripinfo_routeLength"] = df["tripinfo_routeLength"] / 1_000
        df["efficiency"] = df["battery_totalEnergyConsumed"] / df["tripinfo_routeLength"]

        for scenario in ["summer", "winter", "reduced"]:
            subset = df[df["scenario"] == scenario]
            print(scenario)
            print("ebusco",subset[subset["tripinfo_vType"] == "Ebusco 2.2"].describe())
            print("Su12", subset[subset["tripinfo_vType"] == "Solaris Urbino 12"].describe())
            print("Su18", subset[subset["tripinfo_vType"] == "Solaris Urbino 18"].describe())
            vtypes = sorted(subset["tripinfo_vType"].unique())

            data = [subset[subset["tripinfo_vType"] == vtype]["efficiency"] for vtype in vtypes]
            fig, _ = EnergyConsumptionAnalysis._styled_boxplot(
                data, vtypes, xlabel="Vehicle type", ylabel="Energy Efficiency [kWh/km]"
            )
            fig.savefig(os.path.join(output_dir, f"{scenario}_efficiency_plot.pdf"))
            plt.show()

    def energy_efficiency_by_type(output_dir=r"C:\Users\Ralop\Nextcloud\Masterarbeit\Grafiken\Plots"):
        con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")

        df = con.execute("""
            SELECT
                battery_totalEnergyConsumed,
                tripinfo_routeLength,
                tripinfo_vType,
                scenario
            FROM multirun_tripinfo
        """).fetchdf()

        con.close()

        df["battery_totalEnergyConsumed"] = df["battery_totalEnergyConsumed"] / 1_000
        df["tripinfo_routeLength"] = df["tripinfo_routeLength"] / 1_000
        df["efficiency"] = df["battery_totalEnergyConsumed"] / df["tripinfo_routeLength"]

        for scenario in ["summer", "winter", "reduced"]:
            subset = df[df["scenario"] == scenario]
            print(scenario)
            print("ebusco",subset[subset["tripinfo_vType"] == "Ebusco 2.2"].describe())
            print("Su12", subset[subset["tripinfo_vType"] == "Solaris Urbino 12"].describe())
            print("Su18", subset[subset["tripinfo_vType"] == "Solaris Urbino 18"].describe())
            vtypes = sorted(subset["tripinfo_vType"].unique())

            data = [subset[subset["tripinfo_vType"] == vtype]["efficiency"] for vtype in vtypes]
            fig, _ = EnergyConsumptionAnalysis._styled_boxplot(
                data, vtypes, xlabel="Vehicle type", ylabel="Energy Efficiency [kWh/km]"
            )
            fig.savefig(os.path.join(output_dir, f"{scenario}_efficiency_plot.pdf"))
            plt.show()

    def energy_efficiency_over_avg_speed(output_dir=r"C:\Users\Ralop\Nextcloud\Masterarbeit\Grafiken\Plots"):
        con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")
        df = con.execute("""
            SELECT
                battery_totalEnergyConsumed,
                tripinfo_arrival,
                tripinfo_waitingTime,
                tripinfo_depart,
                tripinfo_stopTime,
                tripinfo_routeLength,
                tripinfo_vType,
                scenario
            FROM multirun_tripinfo
        """).fetchdf()
        con.close()


        df["battery_totalEnergyConsumed"] = df["battery_totalEnergyConsumed"] / 1_000
        df["tripinfo_routeLength"] = df["tripinfo_routeLength"] / 1_000
        df["efficiency"] = df["battery_totalEnergyConsumed"] / df["tripinfo_routeLength"]

        df["driving_time"] = (
            df["tripinfo_arrival"].where(
                df["tripinfo_arrival"] != -1,
                104400
            ) 
            - df["tripinfo_depart"] 
            - df["tripinfo_waitingTime"] 
            - df["tripinfo_stopTime"]
            ) / 3600

        df["average_speed"] = df["tripinfo_routeLength"] / df["driving_time"]

        for scenario in ["summer", "winter", "reduced"]:
            subset = df[df["scenario"] == scenario]

            print(scenario)

            fig, ax = plt.subplots(figsize=(10, 6))

            vtypes = sorted(subset["tripinfo_vType"].unique())

            for vtype in vtypes:
                vtype_subset = subset[subset["tripinfo_vType"] == vtype].dropna(
                    subset=["average_speed", "efficiency"]
                )

                scatter = ax.scatter(
                    vtype_subset["average_speed"],
                    vtype_subset["efficiency"],
                    label=vtype,
                    alpha=0.6
                )
                color = scatter.get_facecolor()[0]

                # Linear trend line
                x = vtype_subset["average_speed"].to_numpy()
                y = vtype_subset["efficiency"].to_numpy()

                if len(x) >= 2:
                    slope, intercept = np.polyfit(x, y, 1)

                    x_trend = np.linspace(x.min(), x.max(), 100)
                    y_trend = slope * x_trend + intercept

                    ax.plot(
                        x_trend,
                        y_trend,
                        color=color,
                        linestyle="--",
                        alpha=0.9,
                        linewidth=2
                    )

            ax.set_xlabel("Average Speed [km/h]")
            ax.set_ylabel("Energy Efficiency [kWh/km]")
            ax.set_title(f"Energy Efficiency over Average Speed - {scenario}")
            ax.legend(title="Vehicle type")
            ax.grid(True, alpha=0.3)

            fig.tight_layout()
            fig.savefig(
                os.path.join(output_dir, f"{scenario}_efficiency_over_speed.pdf")
            )

            plt.show()
            plt.close(fig)

    def energy_efficiency_over_avg_speed_stop_correllation(output_dir=r"C:\Users\Ralop\Nextcloud\Masterarbeit\Grafiken\Plots"):
        con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")
        df = con.execute("""
            SELECT
                battery_totalEnergyConsumed,
                tripinfo_arrival,
                tripinfo_waitingTime,
                tripinfo_depart,
                tripinfo_stopTime,
                tripinfo_routeLength,
                tripinfo_vType,
                tripinfo_waitingCount,
                scenario
            FROM multirun_tripinfo
        """).fetchdf()
        con.close()


        df["battery_totalEnergyConsumed"] = df["battery_totalEnergyConsumed"] / 1_000
        df["tripinfo_routeLength"] = df["tripinfo_routeLength"] / 1_000
        df["efficiency"] = df["battery_totalEnergyConsumed"] / df["tripinfo_routeLength"]

        df["driving_time"] = (
            df["tripinfo_arrival"].where(
                df["tripinfo_arrival"] != -1,
                104400
            )
            - df["tripinfo_depart"]
            - df["tripinfo_waitingTime"]
            - df["tripinfo_stopTime"]
            ) / 3600

        df["average_speed"] = df["tripinfo_routeLength"] / df["driving_time"]

        for scenario in ["summer", "winter", "reduced", "storage", "nodepot"]:
            subset = df[df["scenario"] == scenario]

            print(scenario)

            fig, ax = plt.subplots(figsize=(10, 6))

            from matplotlib.lines import Line2D

            vtypes = sorted(subset["tripinfo_vType"].unique())
            markers = ["o", "s", "^", "D", "v", "P", "X", "*", "h", "8"]
            linestyles = ["--", "-", ":", (0, (3, 1, 1, 1)), (0, (5, 1)),
                          (0, (1, 1)), (0, (3, 5, 1, 5)), (0, (5, 5)),
                          (0, (1, 5)), (0, (3, 10, 1, 10))]

            waiting_count_min = subset["tripinfo_waitingCount"].min()
            waiting_count_max = subset["tripinfo_waitingCount"].max()

            legend_handles = []
            trend_lines = []

            for i, vtype in enumerate(vtypes):
                vtype_subset = subset[subset["tripinfo_vType"] == vtype].dropna(
                    subset=["average_speed", "efficiency"]
                )
                marker = markers[i % len(markers)]
                linestyle = linestyles[i % len(linestyles)]

                scatter = ax.scatter(
                    vtype_subset["average_speed"],
                    vtype_subset["efficiency"],
                    c=vtype_subset["tripinfo_waitingCount"],
                    cmap="viridis",
                    vmin=waiting_count_min,
                    vmax=waiting_count_max,
                    marker=marker,
                    edgecolors="black",
                    linewidths=0.5,
                    alpha=0.8
                )
                legend_handles.append(
                    Line2D(
                        [0], [0],
                        marker=marker,
                        linestyle=linestyle,
                        color="black",
                        markerfacecolor="none",
                        markeredgecolor="black",
                        label=vtype
                    )
                )

                # Trend of waiting count over average speed, for the secondary axis
                trend_subset = vtype_subset.dropna(subset=["tripinfo_waitingCount"])
                x2 = trend_subset["average_speed"].to_numpy()
                y2 = trend_subset["tripinfo_waitingCount"].to_numpy()

                if len(x2) >= 2:
                    slope, intercept = np.polyfit(x2, y2, 1)

                    x2_trend = np.linspace(x2.min(), x2.max(), 100)
                    y2_trend = slope * x2_trend + intercept

                    trend_lines.append((x2_trend, y2_trend, linestyle))

            fig.colorbar(scatter, ax=ax, label="Waiting Count", pad=0.12)

            ax.set_xlabel("Average Speed [km/h]")
            ax.set_ylabel("Energy Efficiency [kWh/km]")
            ax.legend(
                handles=legend_handles,
                title="Vehicle type",
                loc="upper center",
                bbox_to_anchor=(0.5, -0.12),
                ncol=min(len(legend_handles), 4)
            )
            ax.grid(True, alpha=0.3)

            fig.tight_layout()

            # Created after the colorbar/tight_layout so it inherits ax's final,
            # already-shrunk position instead of the wider pre-colorbar one.
            ax2 = ax.twinx()
            for x2_trend, y2_trend, linestyle in trend_lines:
                ax2.plot(
                    x2_trend,
                    y2_trend,
                    color="black",
                    linestyle=linestyle,
                    alpha=0.8,
                    linewidth=1.5
                )
            ax2.set_ylabel("Waiting Count (trend)")
            ax2.grid(False)

            fig.savefig(
                os.path.join(output_dir, f"{scenario}_efficiency_over_speed_count.pdf")
            )

            plt.show()
            plt.close(fig)

    def battery_soc_over_time(output_dir=r"C:\Users\Ralop\Nextcloud\Masterarbeit\Grafiken\Plots"):
        con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")

        df = con.execute("""
            SELECT
                bat.timestep_time,
                bat.vehicle_actualBatteryCapacity,
                bat.vehicle_id,
                trip.tripinfo_vType,
                bat.scenario,
                bat.seed
            FROM multirun_battery_aggregated AS bat
            JOIN multirun_tripinfo AS trip
                ON trip.tripinfo_id = bat.vehicle_id
            WHERE bat.seed = 65
            AND trip.seed = 65
            ORDER BY bat.timestep_time, bat.vehicle_id
        """).fetchdf()
        con.close()

        df["timestep_time"] = df["timestep_time"] / 3600
        df["vehicle_actualBatteryCapacity"] = df["vehicle_actualBatteryCapacity"] / 1000

        print(df.head())

        for scenario in ["summer", "winter", "reduced"]:
            fig, ax = plt.subplots(figsize=(10, 6))

            subset = df[df["scenario"] == scenario]

            vtypes = sorted(subset["tripinfo_vType"].unique())
            colors = plt.cm.tab10(range(len(vtypes)))
            color_map = dict(zip(vtypes, colors))

            for vehicle_id, vehicle_subset in subset.groupby("vehicle_id"):
                vehicle_type = vehicle_subset["tripinfo_vType"].iloc[0]
                vehicle_subset = vehicle_subset.sort_values("timestep_time")

                ax.plot(
                    vehicle_subset["timestep_time"],
                    vehicle_subset["vehicle_actualBatteryCapacity"],
                    color=color_map[vehicle_type],
                    alpha=0.3,
                    linewidth=0.3,
                )

            # Create legend entries for vehicle types
            for vtype in vtypes:
                ax.plot(
                    [],
                    [],
                    color=color_map[vtype],
                    label=vtype,
                    linewidth=1.5,
                )

            ax.set_xlabel("Time [h]")
            ax.set_ylabel("Battery SoC [kWh]")
            ax.set_title(f"Battery SoC over Time - {scenario}")
            ax.legend(title="Vehicle type")
            ax.grid(True, alpha=0.2)

            fig.tight_layout()
            fig.savefig(
                os.path.join(output_dir, f"{scenario}_battery_soc_over_time.pdf")
            )

            plt.show()
            plt.close(fig)


    def energy_efficiency_over_stop_count(output_dir=r"C:\Users\Ralop\Nextcloud\Masterarbeit\Grafiken\Plots"):
        con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")
        df = con.execute("""
            SELECT
                battery_totalEnergyConsumed,
                tripinfo_routeLength,
                tripinfo_vType,
                tripinfo_waitingCount,
                scenario
            FROM multirun_tripinfo
        """).fetchdf()
        con.close()

        df["battery_totalEnergyConsumed"] = df["battery_totalEnergyConsumed"] / 1_000
        df["tripinfo_routeLength"] = df["tripinfo_routeLength"] / 1_000
        df["efficiency"] = df["battery_totalEnergyConsumed"] / df["tripinfo_routeLength"]

        for scenario in ["summer", "winter", "reduced"]:
            subset = df[df["scenario"] == scenario]

            print(scenario)

            fig, ax = plt.subplots(figsize=(10, 6))

            vtypes = sorted(subset["tripinfo_vType"].unique())

            for i, vtype in enumerate(vtypes):
                color = PALETTE[i % len(PALETTE)]
                vtype_subset = subset[subset["tripinfo_vType"] == vtype].dropna(
                    subset=["tripinfo_waitingCount", "efficiency"]
                )

                ax.scatter(
                    vtype_subset["tripinfo_waitingCount"],
                    vtype_subset["efficiency"],
                    color=color,
                    alpha=0.15,
                    linewidths=0,
                )

                x = vtype_subset["tripinfo_waitingCount"].to_numpy()
                y = vtype_subset["efficiency"].to_numpy()

                if len(x) >= 2:
                    slope, intercept = np.polyfit(x, y, 1)

                    x_trend = np.linspace(x.min(), x.max(), 100)
                    y_trend = slope * x_trend + intercept

                    ax.plot(
                        x_trend,
                        y_trend,
                        color=color,
                        label=vtype,
                        linewidth=2,
                    )

            ax.set_xlabel("Number of Stops")
            ax.set_ylabel("Energy Efficiency [kWh/km]")
            ax.legend(title="Vehicle type")
            ax.grid(True, alpha=0.3)

            fig.tight_layout()

            fig.savefig(
                os.path.join(output_dir, f"{scenario}_efficiency_over_stop_count.pdf")
            )

            plt.show()
            plt.close(fig)

if __name__ == "__main__":
    EnergyConsumptionAnalysis.stop_duration_bar_chart(bus_id="bus_1055")


