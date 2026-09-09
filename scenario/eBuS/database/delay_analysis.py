import os

import duckdb
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
import pandas as pd

class DelayAnalysis:

    def trip_delay_over_time(output_dir=r"C:\Users\Ralop\Nextcloud\Masterarbeit\Grafiken\Plots"):
            con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")

            df = con.execute("""
                SELECT
                    stopinfo_delay,
                    stopinfo_id,
                    stopinfo_started,
                    scenario,
                    seed
                FROM multirun_stopinfo
                WHERE seed = 65
                ORDER BY stopinfo_started
            """).fetchdf()

            con.close()

            df = df[df["stopinfo_delay"] > -1e6]
            df = df[df["stopinfo_started"] != 0]

            df["stopinfo_delay"] = df["stopinfo_delay"] / 60
            df["stopinfo_started"] = df["stopinfo_started"] / 3600

            for scenario in ["summer", "winter", "reduced"]:
                subset = df[df["scenario"] == scenario]

                fig, ax = plt.subplots(figsize=(16, 10))

                groups = list(subset.groupby("stopinfo_id", sort=False))
                colors = plt.get_cmap("turbo")(np.linspace(0, 1, len(groups)))

                for (_, vehicle), color in zip(groups, colors):
                    vehicle = vehicle.sort_values("stopinfo_started")
                    ax.plot(
                        vehicle["stopinfo_started"],
                        vehicle["stopinfo_delay"],
                        color=color,
                        alpha=0.8,
                        linewidth=0.4,
                    )

                ax.set_xlabel("Time [h]")
                ax.set_ylabel("Delay [min]")
                ax.grid(True, alpha=0.2)

                fig.tight_layout()
                fig.savefig(
                    os.path.join(output_dir, f"{scenario}_delay_over_time.pdf")
                )

                plt.show()
                plt.close(fig)

    def delay_deviation():
            con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")

            df = con.execute("""
                SELECT
                    stopinfo_delay,
                    stopinfo_id,
                    stopinfo_started,
                    scenario,
                    seed
                FROM multirun_stopinfo
                ORDER BY stopinfo_started
            """).fetchdf()

            con.close()

            df = df[df["stopinfo_delay"] > -1e6]

            mean_delay_per_scenario = {}

            for scenario in ["summer", "winter", "reduced"]:
                subset = df[df["scenario"] == scenario]
                mean_delay_per_run = subset.groupby("seed")["stopinfo_delay"].mean()
                std = mean_delay_per_run.std(ddof=1)
                print(f"{scenario}: mean delay per run={mean_delay_per_run.to_dict()}, std across runs={std:.3f}")
                mean_delay_per_scenario[scenario] = mean_delay_per_run.mean()

            std_across_scenarios = pd.Series(mean_delay_per_scenario).std(ddof=1)
            print(f"mean delay per scenario={mean_delay_per_scenario}, std across scenarios={std_across_scenarios:.3f}")

    def cumulative_delay_deviation():
        con = duckdb.connect(r"G:\Dokumente\Studium\FU Berlin\BeSTeBuS\best-ebus\scenario\eBuS\database\eBuS.duckdb")

        df = con.execute("""
            SELECT
                stopinfo_delay,
                stopinfo_id,
                stopinfo_started,
                scenario,
                seed
            FROM multirun_stopinfo
            ORDER BY stopinfo_started
        """).fetchdf()

        con.close()

        df = df[df["stopinfo_delay"] > -1e6]
        df = df[df["stopinfo_started"] != 0]

        #df["stopinfo_delay"] = df["stopinfo_delay"] / 60
        df["stopinfo_started"] = df["stopinfo_started"] / 3600

        mean_delay_per_scenario = {}

        for scenario in ["summer", "winter", "reduced"]:
            subset = df[df["scenario"] == scenario]
            mean_delay_per_run = subset.groupby("seed")["stopinfo_delay"].mean()
            std = mean_delay_per_run.std(ddof=1)
            print(f"{scenario}: mean delay per run={mean_delay_per_run.to_dict()}, std across runs={std:.3f}")
            mean_delay_per_scenario[scenario] = mean_delay_per_run.mean()

        std_across_scenarios = pd.Series(mean_delay_per_scenario).std(ddof=1)
        print(f"mean delay per scenario={mean_delay_per_scenario}, std across scenarios={std_across_scenarios:.3f}")

if __name__ == "__main__":
    DelayAnalysis.delay_deviation()
