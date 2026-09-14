from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATABASE_PATH = "best-ebus/scenario/eBuS/database/eBuS.duckdb"
OUTPUT_PATH = Path(r"C:\Users\svens\Nextcloud\Masterarbeit\Grafiken\NewPlots")
VEHICLE_DICT = {
    "Ebusco2.2electric12m": "Ebusco 2.2",
    "SolarsisUrbino12electric": "Urbino 12",
    "SolarsisUrbino18electric": "Urbino 18",
}
SCENARIOS = ["summer", "winter", "reduced", "increased"]


class EfficiencyPerType:
    """Energy efficiency (kWh/km) per vehicle type, broken down by scenario."""

    def __init__(
        self,
        database_path=DATABASE_PATH,
        output_path=OUTPUT_PATH,
        vehicle_dict=VEHICLE_DICT,
        scenarios=SCENARIOS,
    ):
        self.database_path = database_path
        self.output_path = Path(output_path)
        self.vehicle_dict = vehicle_dict
        self.scenarios = scenarios
        self.df = pd.DataFrame()
        self.outlier_rows = []  # collects per-seed outlier counts across all scenarios

    def load_data(self):
        con = duckdb.connect(self.database_path)

        scenario_list = ", ".join(f"'{s}'" for s in self.scenarios)
        df = con.execute(f"""
            SELECT
                tripinfo_id,
                seed,
                battery_totalEnergyConsumed,
                battery_totalEnergyRegenerated,
                tripinfo_routeLength,
                tripinfo_vType,
                scenario
            FROM multirun_tripinfo
            WHERE scenario IN ({scenario_list})
        """).fetchdf()

        con.close()

        df["battery_totalEnergyConsumed"] = df["battery_totalEnergyConsumed"] / 1000
        df["battery_totalEnergyRegenerated"] = df["battery_totalEnergyRegenerated"] / 1000
        df["tripinfo_routeLength"] = df["tripinfo_routeLength"] / 1000

        # Energy consumed per distance
        df["energy_efficiency"] = (
            (df["battery_totalEnergyConsumed"] - df["battery_totalEnergyRegenerated"])
            / df["tripinfo_routeLength"]
        )

        self.df = df
        return df

    @staticmethod
    def iqr_bounds(values, whis=1.5):
        """Same rule matplotlib's boxplot uses by default (whis=1.5)."""
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        return q1 - whis * iqr, q3 + whis * iqr

    def _report_outliers(self, subset, vtypes, boxplot_data, bp, scenario):
        print(f"\n{'=' * 70}")
        print(f"Outliers per vehicle type — {scenario.upper()}")
        print("=" * 70)

        for i, vtype in enumerate(vtypes):
            n_outliers = len(bp["fliers"][i].get_ydata())
            n_total = len(boxplot_data[i])
            print(
                f"{self.vehicle_dict.get(vtype, vtype)}: "
                f"{n_outliers} outliers / {n_total} trips "
                f"({n_outliers / n_total:.1%})"
            )

            # ---- Break down outliers by seed for this vtype ----
            vsub = subset.loc[
                subset["tripinfo_vType"] == vtype,
                ["seed", "energy_efficiency"]
            ].dropna(subset=["energy_efficiency"])

            lower, upper = self.iqr_bounds(vsub["energy_efficiency"].values)
            vsub = vsub.assign(
                is_outlier=(vsub["energy_efficiency"] < lower) | (vsub["energy_efficiency"] > upper)
            )

            seed_counts = (
                vsub.groupby("seed")["is_outlier"]
                .agg(n_outliers="sum", n_total="count")
                .reset_index()
            )
            seed_counts = seed_counts[seed_counts["n_outliers"] > 0].sort_values(
                "n_outliers", ascending=False
            )

            if not seed_counts.empty:
                print(f"    Outliers by seed ({self.vehicle_dict.get(vtype, vtype)}):")
                for _, row in seed_counts.iterrows():
                    print(
                        f"      seed {row['seed']}: "
                        f"{int(row['n_outliers'])} / {int(row['n_total'])} trips"
                    )

            seed_counts["scenario"] = scenario
            seed_counts["vType"] = self.vehicle_dict.get(vtype, vtype)
            self.outlier_rows.append(seed_counts)

    def _style_boxplot(self, ax, bp, vtypes, positions):
        # Different color for each vehicle type
        cmap = plt.get_cmap("tab10")

        for i, box in enumerate(bp["boxes"]):
            box.set_facecolor(cmap(i % 10))
            box.set_alpha(0.7)

        ax.set_xticks(positions)
        ax.set_xticklabels(
            [self.vehicle_dict.get(vtype, vtype) for vtype in vtypes],
            rotation=45,
            ha="right"
        )

        ax.set_xlim(positions[0] - 0.2, positions[-1] + 0.2)

        ax.set_xlabel("Vehicle Type")
        ax.set_ylabel("Energy Efficiency")

        ax.grid(axis="y", alpha=0.3)

    def _print_statistics(self, subset, vtypes, scenario):
        print("\n" + "=" * 70)
        print(f"Energy efficiency statistics — {scenario.upper()}")
        print("=" * 70)

        for vtype in vtypes:
            values = subset.loc[
                subset["tripinfo_vType"] == vtype,
                "energy_efficiency"
            ].dropna()

            print(f"\nVehicle type: {self.vehicle_dict.get(vtype, vtype)}")
            print("-" * 40)
            print(values.describe().to_string())

    def _save_figure(self, fig, scenario):
        fig.tight_layout()

        output_file = self.output_path / f"energy_efficiency_{scenario}.pdf"

        fig.savefig(output_file, format="pdf", bbox_inches="tight")

        plt.show()
        plt.close(fig)

        print(f"\nSaved: {output_file}")

    def plot_scenario(self, scenario):
        fig, ax = plt.subplots(figsize=(13, 8))

        subset = self.df[self.df["scenario"] == scenario].copy()

        # Keep vehicle types in a consistent order
        vtypes = sorted(subset["tripinfo_vType"].dropna().unique())

        # Data for each vehicle type
        boxplot_data = [
            subset.loc[
                subset["tripinfo_vType"] == vtype,
                "energy_efficiency"
            ].dropna()
            for vtype in vtypes
        ]

        positions = np.arange(1, len(vtypes) + 1) * 0.3

        # Create boxplots
        bp = ax.boxplot(
            boxplot_data,
            positions=positions,
            patch_artist=True,
            medianprops={"color": "black", "linewidth": 1.5}
        )

        self._report_outliers(subset, vtypes, boxplot_data, bp, scenario)
        self._style_boxplot(ax, bp, vtypes, positions)
        self._print_statistics(subset, vtypes, scenario)
        self._save_figure(fig, scenario)

    def summarize_outliers(self):
        outlier_summary = pd.concat(self.outlier_rows, ignore_index=True)
        outlier_summary = outlier_summary[
            ["scenario", "vType", "seed", "n_outliers", "n_total"]
        ].sort_values(["scenario", "vType", "n_outliers"], ascending=[True, True, False])

        print("\n" + "=" * 70)
        print("Summary: seeds contributing outliers (all scenarios)")
        print("=" * 70)
        print(outlier_summary.to_string(index=False))

        return outlier_summary

    def run(self):
        self.load_data()

        for scenario in self.scenarios:
            self.plot_scenario(scenario)

        return self.summarize_outliers()


if __name__ == "__main__":
    EfficiencyPerType().run()
