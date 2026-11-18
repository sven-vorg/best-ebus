# Dashboard creation
# Pulls data from database and writes a compact text dashboard
import io
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", None)

FMT = "{:.6f}".format


class TextDashboard:

    def __init__(self, database: Path, output: Path):
        self.output = output
        self.con = duckdb.connect(str(database), read_only=True)

    # Context manager helpers
    def close(self):
        self.con.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ------------------------------------------------------------------ #
    def infrastructure_details(self):
        df = self.con.execute("""
            WITH stations AS (
                SELECT scenario, COUNT(DISTINCT chargingEvent_chargingStationId) AS stations
                FROM multirun_chargingstations GROUP BY scenario
            ),
            trips AS (
                SELECT scenario, COUNT(DISTINCT tripinfo_id) AS vehicles
                FROM multirun_tripinfo GROUP BY scenario
            )
            SELECT scenario, stations, vehicles
            FROM stations JOIN trips USING (scenario)
            ORDER BY scenario
        """).fetchdf()
        print(df.to_string(index=False))

    # ------------------------------------------------------------------ #
    def vehicle_delays(self):
        df = self.con.execute("""
            SELECT stopinfo_delay / 60.0 AS delay, scenario, seed
            FROM multirun_stopinfo
            WHERE stopinfo_delay >= 0
        """).fetchdf()

        # One row per (scenario, seed): mean and max delay in minutes
        per_run = df.groupby(["scenario", "seed"])["delay"].agg(mean="mean", max="max")
        print("Per run (minutes):")
        print(per_run.to_string(float_format=FMT))

        # One row per scenario: aggregated across runs (population std, ddof=0)
        summary = per_run.groupby("scenario").agg(
            runs=("mean", "size"),
            mean_delay=("mean", "mean"),
            std_of_mean=("mean", lambda s: s.std(ddof=0)),
            mean_max_delay=("max", "mean"),
            std_of_max=("max", lambda s: s.std(ddof=0)),
        )
        print("\nPer scenario (across runs):")
        print(summary.to_string(float_format=FMT))

        std_across_scenarios = summary["mean_delay"].std(ddof=0)
        print(f"\nStd of mean delay across scenarios: {std_across_scenarios:.3f}")

    # ------------------------------------------------------------------ #
    @staticmethod
    def _decompose(g: pd.DataFrame) -> pd.Series:
        """Within/between-seed variance decomposition for one (scenario, vtype)."""
        n = g["count"].astype(float)
        N = n.sum()
        grand_mean = (n * g["mean"]).sum() / N
        within = (n * g["std"].fillna(0) ** 2).sum() / N          # E[Var(Y|Seed)]
        between = (n * (g["mean"] - grand_mean) ** 2).sum() / N   # Var(E[Y|Seed])
        total = within + between
        return pd.Series({
            "N": int(N),
            "within": within,
            "between": between,
            "total": total,
            "total_sd": total ** 0.5,
            "between_pct": 100 * between / total if total > 0 else float("nan"),
        })
    # ------------------------------------------------------------------ #
    def vehicle_energy_efficicency(self):
        df = self.con.execute("""
            SELECT battery_totalEnergyConsumed AS consumed,
                   battery_totalEnergyRegenerated AS regenerated,
                   tripinfo_routeLength AS length,
                   tripinfo_vType AS vtype,
                   scenario, seed
            FROM multirun_tripinfo
        """).fetchdf()

        # Net energy consumed per distance
        df["efficiency"] = (df["consumed"] - df["regenerated"]) / df["length"]

        # One row per (scenario, vtype, seed)
        stats = (
            df.dropna(subset=["vtype", "efficiency"])
              .groupby(["scenario", "vtype", "seed"])["efficiency"]
              .agg(mean="mean", std="std", count="count")
        )

        # Across seeds, per (scenario, vtype)
        summary = stats.groupby(level=["scenario", "vtype"]).agg(
            seeds=("mean", "size"),
            vehicles=("count", "sum"),
            mean_of_means=("mean", "mean"),
            std_of_means=("mean", "std"),
            avg_within_std=("std", "mean"),
        )
        print("Energy efficiency per scenario / vehicle type (across seeds):")
        print(summary.to_string(float_format=FMT))

        decomp = stats.groupby(level=["scenario", "vtype"]).apply(self._decompose)
        decomp["N"] = decomp["N"].astype(int)
        print("\nVariance decomposition by seed (between_pct = ICC in %):")
        print(decomp.to_string(float_format=FMT))

    # ------------------------------------------------------------------ #
    def total_energy_consumption(self):
        df = self.con.execute("""
            SELECT battery_totalEnergyConsumed AS consumed,
                   battery_totalEnergyRegenerated AS regenerated,
                   scenario, seed
            FROM multirun_tripinfo
        """).fetchdf()

        # Net energy per (scenario, seed), converted to MWh
        per_run = (
            df.groupby(["scenario", "seed"])[["consumed", "regenerated"]].sum()
              .assign(net_mwh=lambda d: (d["consumed"] - d["regenerated"]) / 1_000_000)
        )
        print("Net energy consumed per run (MWh):")
        print(per_run[["net_mwh"]].to_string(float_format=FMT))

        # Across seeds, per scenario
        summary = per_run.groupby("scenario")["net_mwh"].agg(
            runs="count", mean="mean", std="std", min="min", median="median", max="max"
        )
        print("\nPer scenario (across seeds, MWh):")
        print(summary.to_string(float_format=FMT))
    # ------------------------------------------------------------------ #
    def ses_energy_statistics(self, scenarios=("summer", "winter")):
        # Sum in the database (the table holds ~5M rows per scenario/seed), Wh -> kWh
        sums = ", ".join(f"SUM({c}) / 1000 AS {c.removeprefix('station_')}" for c in SES_ENERGY_COLS)
        per_run = self.con.execute(f"""
            SELECT scenario, seed, {sums}
            FROM multirun_ses
            WHERE scenario IN (SELECT UNNEST(?))
              AND seed IN (SELECT UNNEST(?))
              AND station_chargingStationId NOT IN {DEPOT_IDS}
            GROUP BY scenario, seed
            ORDER BY scenario, seed
        """, [list(scenarios), SEEDS]).fetchdf().set_index(["scenario", "seed"])

        print("SES energy per run (kWh):")
        print(per_run.to_string(float_format=FMT))

        # Across seeds, per scenario
        summary = per_run.groupby("scenario").agg(["mean", "std"])
        print("\nPer scenario (across seeds, kWh):")
        print(summary.T.to_string(float_format=FMT))
        return per_run, summary
    def create_dashboard(self, filename: str = "dashboard.txt") -> Path:
        """Runs all dashboard functions and writes their results to a text file."""
        sections = [
            ("INFRASTRUCTURE DETAILS", self.infrastructure_details),
            ("VEHICLE DELAYS", self.vehicle_delays),
            ("VEHICLE ENERGY EFFICIENCY", self.vehicle_energy_efficicency),
            ("TOTAL ENERGY CONSUMPTION", self.total_energy_consumption),
            ("SES ENERGY STATISTICS", self.ses_energy_statistics),
        ]

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print(f"DASHBOARD — generated {datetime.now():%Y-%m-%d %H:%M:%S}")
            for title, func in sections:
                print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")
                func()

        self.output.mkdir(parents=True, exist_ok=True)
        out_file = self.output / filename
        out_file.write_text(buffer.getvalue(), encoding="utf-8")
        return out_file


if __name__ == "__main__":
    with TextDashboard(
        database=Path("best-ebus/scenario/eBuS/database/ebus.duckdb"),
        output=Path("best-ebus/scenario/dashboards"),
    ) as dash:
        dash.create_dashboard()