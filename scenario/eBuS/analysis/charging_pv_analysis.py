from dotenv import load_dotenv
import pandas as pd
import numpy as np
import os

from sumo_xml import parse_sumo_xml, to_numeric_columns


class ChargingPVAnalysis:
    """
    Combines per-station charging energy (SUMO output, long format) with
    hourly PV generation (wide format) into a per-station, per-time-step
    'change' value, then turns that into an absolute battery state of
    charge (ESS = Energy Storage System) over time.

    UNITS: everything is normalized to Wh (watt-hours) before being
    combined, including the starting `ess` value (500 kWh == 500000 Wh).

    Big picture pipeline:
        1. Load raw PV data (wide) and raw SUMO charging data (long).
        2. Reshape PV data from wide -> long so it has the same shape
           as the charging data (one row per station per time step).
        3. Clean the SUMO charging data (fix types, fill missing values
           with 0 instead of dropping rows).
        4. Bucket each individual charging "step" into the hourly PV
           time step it belongs to, and sum energy within each bucket.
        5. Merge PV generation and charging energy together and compute
           the net "change" in energy for each station/time step, all
           in Wh:
               change = (PV energy generated that second, in Wh)
                        - (energy charged that step, in Wh)
        6. Turn "change" into an absolute battery level ("ess_absolute")
           by accumulating changes over time, starting from an initial
           ess value (in Wh).
        7. Package everything into a results dict and write it to CSV.
    """

    def __init__(self, pv_path: str, stations_path: str, ess: float,
                 ess_max: float = None, battery_path: str = None):
        self.pv_path = pv_path
        self.stations_path = stations_path      # chargingsstations.xml (raw SUMO output)
        self.battery_path = battery_path        # battery.xml (raw SUMO output), optional

        self.pv_generation = None      # wide: station_id x time-step columns
        self.stations = None           # long: raw charging-step rows
        self.vehicle_battery = None    # long: vehicle_id, timestep_time, vehicle_totalEnergyConsumed
        self.pv_long = None            # long: station_id, step_time, pv_power
        self.energy_per_bucket = None  # station_id, pv_time_step, step_energyCharged
        self.merged = None             # final merged table
        self.results = None            # {station_id: [(time_step, change, ess_absolute), ...]}
        self.ess = ess                 # starting battery state of charge, in Wh
                                        # (e.g. 500 kWh -> pass in 500000.0)
        # Battery capacity ceiling, in Wh. Defaults to the starting
        # ess value if not given separately (battery starts full).
        self.ess_max = ess_max if ess_max is not None else ess

    # ---------------------------------------------------------------
    # Loading
    # ---------------------------------------------------------------
    def load_data(self):
        """
        Read the PV generation file (still a plain CSV) and parse the
        raw SUMO XML outputs directly - no intermediate CSV conversion
        (e.g. SUMO's own xml2csv.py tool) required.

        pv_generation: CSV, comma-separated. Wide format:
            station_id | 3600 | 7200 | 10800 | ...
            station_A  | 12.5 | 14.0 | 9.2    | ...
        Each non-"station_id" column header is a time step (in seconds),
        and each cell is the PV power generated (in kW, hourly average)
        for that station during that hour. This gets converted to Wh
        in merge_and_compute().

        stations (chargingsstations.xml): SUMO's charging-station
        output. Structure:
            <chargingStation id="cs_0">
                <step time="10.00" energyCharged="0.05" .../>
            </chargingStation>
        parse_sumo_xml flattens this into one row per <step>, with
        columns "chargingStation_id", "step_time",
        "step_energyCharged", etc. - matching the column names the
        rest of the pipeline (clean_stations, bucket_charging_steps)
        already expects.

        vehicle_battery (battery.xml, optional): SUMO's battery
        output. Structure:
            <timestep time="1.00">
                <vehicle id="0" totalEnergyConsumed="1.87" .../>
            </timestep>
        parse_sumo_xml flattens this into one row per <vehicle>, with
        columns "timestep_time", "vehicle_id",
        "vehicle_totalEnergyConsumed", etc. (used by the dashboard's
        "Top Energy Consumers" panel). Only loaded if battery_path was
        given to __init__.
        """
        self.pv_generation = pd.read_csv(self.pv_path)

        self.stations = parse_sumo_xml(self.stations_path, row_tag="step")
        # step_time/step_energyCharged come in as strings from XML
        # attributes; clean_stations() already coerces both of these
        # to numeric (and fills missing values with 0), so no extra
        # conversion is needed here.

        if self.battery_path is not None:
            vehicle_battery = parse_sumo_xml(self.battery_path, row_tag="vehicle")
            self.vehicle_battery = to_numeric_columns(
                vehicle_battery, ["timestep_time", "vehicle_totalEnergyConsumed"]
            )

        return self

    # ---------------------------------------------------------------
    # PV: wide -> long
    # ---------------------------------------------------------------
    def build_pv_long(self):
        """
        Reshape pv_generation from wide (one column per time step) into
        long format (one row per station per time step), so it can be
        merged with the charging data later.

        Before (wide):
            station_id | 3600 | 7200
            A          | 12.5 | 14.0

        After (long):
            station_id | step_time | pv_power
            A          | 3600      | 12.5
            A          | 7200      | 14.0

        melt() does this reshape: id_vars=station_id stays as an
        identifier column, and every other column becomes two columns
        - "step_time" (the old column header) and "pv_power" (the old
        cell value, still in kW at this point - converted to Wh later).
        """
        time_columns = [c for c in self.pv_generation.columns if c != "station_id"]

        pv_long = self.pv_generation.melt(
            id_vars="station_id",
            value_vars=time_columns,
            var_name="step_time",
            value_name="pv_power",
        )

        # Column headers come in as strings (e.g. "3600"), so convert
        # step_time to an actual integer for numeric comparisons/merges later.
        pv_long["step_time"] = pv_long["step_time"].astype(int)

        self.pv_long = pv_long
        return self

    # ---------------------------------------------------------------
    # Stations: clean + bucket into PV time steps
    # ---------------------------------------------------------------
    def clean_stations(self):
        """
        The raw SUMO output contains some rows that are NOT real
        charging steps — e.g. a per-station summary row like:
            "0;cd_Cicerostrasse_01;0.00;;;;;;;;;;;;;"
        which has an empty step_time.

        Rather than dropping these rows (which would discard them
        entirely), we fill missing values with 0:
        1. pd.to_numeric(..., errors="coerce") converts step_time and
           step_energyCharged to numbers; anything that can't be
           converted (e.g. an empty string) becomes NaN instead of
           raising an error.
        2. fillna(0) on step_time means a summary/junk row with no
           real time just gets treated as time 0 (which later gets
           bucketed into the first hour, 3600, with 0 energy charged)
           instead of being dropped - so no row, and no potential PV
           generation for that time step, is ever skipped.
        3. fillna(0) on step_energyCharged means a real step with a
           missing energy value is treated as "no energy charged in
           this step" rather than "unknown."
        """
        stations = self.stations.copy()

        stations["step_time"] = pd.to_numeric(
            stations["step_time"], errors="coerce"
        ).fillna(0)
        stations["step_energyCharged"] = pd.to_numeric(
            stations["step_energyCharged"], errors="coerce"
        ).fillna(0)

        self.stations = stations
        return self

    def bucket_charging_steps(self):
        """
        The PV data is bucketed into hourly time steps (3600, 7200,
        10800, ...), but individual SUMO charging steps can happen at
        ANY second (e.g. step_time = 4123). We need to assign each
        charging step to the hourly bucket it belongs to, so it can
        later be compared/merged with the matching PV hour.

        Rule: a charging step at step_time T belongs to the *next*
        multiple of 3600 that is >= T. For example:
            step_time = 0 or 1 -> bucket 3600   (first hour: seconds 1-3600)
            step_time = 3600   -> bucket 3600   (exactly on the boundary)
            step_time = 3601   -> bucket 7200   (just past the boundary)
            step_time = 7200   -> bucket 7200

        How the math works:
            np.ceil(step_time / 3600) * 3600

        Example with step_time = 4123:
            4123 / 3600      = 1.145...
            ceil(1.145...)   = 2
            2 * 3600         = 7200   <- correct bucket

        Example with step_time = 3600 (exact boundary):
            3600 / 3600      = 1.0
            ceil(1.0)        = 1
            1 * 3600         = 3600   <- stays in the same bucket

        Special case: step_time = 0 (including former junk rows that
        were filled to 0 in clean_stations) would give:
            0 / 3600 = 0 -> ceil(0) = 0 -> bucket 0
        But bucket "0" doesn't exist in the PV data (buckets start at
        3600). So we clip step_time to a minimum of 1 BEFORE dividing,
        which forces step_time = 0 to behave like step_time = 1, and
        land in bucket 3600 instead of bucket 0.

        After computing pv_time_step for every row, we group by
        (chargingStation_id, pv_time_step) and sum step_energyCharged.
        This handles the case where multiple charging steps for the
        same station fall into the same hour — e.g. three separate
        SUMO steps all within seconds 3601-7200 get added together
        into one total for that station's 7200 bucket.
        """
        stations = self.stations.copy()

        stations["pv_time_step"] = (
            np.ceil(stations["step_time"].clip(lower=1) / 3600) * 3600
        ).astype(int)

        self.energy_per_bucket = (
            stations.groupby(["chargingStation_id", "pv_time_step"])["step_energyCharged"]
            .sum()
            .reset_index()
        )
        return self

    # ---------------------------------------------------------------
    # Merge + compute
    # ---------------------------------------------------------------
    def merge_and_compute(self):
        """
        Combine PV generation (pv_long) with charging energy
        (energy_per_bucket) into one table, then compute the net
        "change" in battery energy for each station/time step, all in
        Wh (to match step_energyCharged and self.ess).

        We use pv_long as the LEFT side of the merge (how="left") so
        that EVERY station/time-step combination from the PV file is
        kept in the result — even hours where a station had zero
        charging activity. If we merged the other way, hours with no
        charging events would disappear entirely.

        merge keys:
            left:  station_id, step_time     (from pv_long)
            right: chargingStation_id, pv_time_step  (from energy_per_bucket)
        These are the same concept under different column names — the
        station identifier and the hourly bucket — so rows are matched
        up correctly across the two tables.

        After merging, any station/time-step pair that had NO matching
        charging row gets step_energyCharged = NaN (no match found).
        fillna(0) turns that into "0 energy charged," which is the
        correct interpretation (no charging happened, not "unknown").

        Then we compute the "change" column, converting pv_power (kW,
        hourly average) into Wh generated per one-second step:

            change = (pv_power * 1000 / 3600) - step_energyCharged

        Why two conversions on pv_power?

        (a) kW -> W: pv_power is measured in kilowatts (kW, hourly
            average power), but we want everything in Wh to match
            step_energyCharged and self.ess. First convert kW to W:
                pv_power [kW] * 1000 = pv_power [W]

        (b) per-hour -> per-second: pv_power (now in W) represents an
            average POWER over the whole hour, i.e. Wh generated per
            hour. Since 1s = 1 time_step, step_energyCharged is a
            per-second (per-step) quantity in Wh. To convert the
            hourly W rate into a per-second Wh amount, divide by 3600
            (seconds per hour):
                pv_power [W] / 3600 [s/hour] = pv_power [Wh per second]

        Combined, both conversions together look like:
                pv_power [kW] * 1000 / 3600

        Example:
            pv_power = 12.5 kW  (average that hour)
            step_energyCharged = 2 Wh (charged in that one step)

            Step (a): 12.5 * 1000         = 12500     W
            Step (b): 12500 / 3600        = 3.4722...  Wh per second

            change = 3.4722... - 2
                   = 1.4722...  (net Wh gained that second/step)

        A positive "change" means the battery gained more energy from
        PV than it lost to charging buses; a negative "change" means
        it lost more (e.g. no sun, but a bus was charging).
        """
        merged = self.pv_long.merge(
            self.energy_per_bucket,
            left_on=["station_id", "step_time"],
            right_on=["chargingStation_id", "pv_time_step"],
            how="left",
        )
        merged["step_energyCharged"] = merged["step_energyCharged"].fillna(0)

        # (a) kW -> W, (b) per-hour -> per-second, result in Wh
        pv_power_wh = (merged["pv_power"] * 1000) / 3600

        merged["change"] = pv_power_wh - merged["step_energyCharged"]

        # Sort so that, per station, rows are in chronological order —
        # this matters a lot for the next step (cumulative sum).
        self.merged = merged.sort_values(["station_id", "step_time"])
        return self

    def calculate_absolute(self):
        """
        Turn the per-step "change" values (in Wh) into an absolute
        battery state of charge ("ess_absolute", in Wh) over time,
        per station, capped to self.ess_max (500000 Wh / 500 kWh).

        Important detail: the ess value shown AT a given time step
        should reflect everything that happened BEFORE that step, not
        including that step's own change. In other words:

            ess_absolute[t] = clip(ess_absolute[t-1] + change[t-1],
                                    0, ess_max)

        Worked example (ess_start = 500000 Wh, ess_max = 500000 Wh):
            step=3600,  change=+50  -> ess_absolute = 500000   (nothing has
                                        happened yet, so still the start
                                        value. The battery is already full,
                                        so this +50 Wh of PV can't be
                                        stored - it's curtailed/lost.)
            step=7200,  change=-10  -> ess_absolute = min(500000, 500000+50)
                                                     = 500000   (the +50 from
                                        the previous step was capped away,
                                        so it was never actually added)
            step=10400, change=5    -> ess_absolute = min(500000, 500000-10)
                                                     = 499990   (this time
                                        the change fits under the cap, so
                                        it's applied normally)

        Why this can't be a plain cumsum() + shift() anymore:
        Capping is PATH-DEPENDENT - once the battery hits ess_max, any
        extra energy that would push it over the cap is lost for good,
        not "banked" for later. A plain cumsum() keeps accumulating the
        uncapped total internally, so clipping the *final* numbers
        after the fact would be wrong: the battery would look like it
        instantly "remembers" energy it never actually stored the
        moment change turns negative again. Each step's capped result
        has to be computed from the PREVIOUS step's already-capped
        result, so we walk through the steps in order instead of using
        a vectorized cumulative sum.

        Grouping by "station_id" throughout ensures each station's
        battery is tracked independently — one station's charging
        history never leaks into another station's accumulation.
        """
        self.merged = self.merged.sort_values(["station_id", "step_time"]).reset_index(drop=True)

        def accumulate_capped(changes: pd.Series) -> pd.Series:
            values = []
            current = self.ess
            for change in changes:
                # Record the level BEFORE this step's change is applied.
                values.append(current)
                # Apply the change, then clip to [0, ess_max] so the
                # battery can neither overflow past capacity nor go
                # negative.
                current = min(self.ess_max, max(0.0, current + change))
            return pd.Series(values, index=changes.index)

        self.merged["ess_absolute"] = (
            self.merged.groupby("station_id")["change"]
            .transform(accumulate_capped)
        )
        return self

    # ---------------------------------------------------------------
    # Results
    # ---------------------------------------------------------------
    def build_results(self):
        """
        Collapse the merged table into a dictionary keyed by station:

            {
                "station_A": [(3600, change_1, ess_1), (7200, change_2, ess_2), ...],
                "station_B": [...],
                ...
            }

        Rather than groupby(...).apply(lambda g: ...), which pandas
        has started deprecating/warning about for this kind of
        row-collecting pattern, we explicitly select only the columns
        we need and turn each station's group into a list of plain
        tuples via itertuples(). itertuples(index=False, name=None)
        yields plain tuples (step_time, change, ess_absolute) without
        the extra pandas Index or named-tuple overhead.
        """
        columns_needed = ["step_time", "change", "ess_absolute"]

        self.results = {
            station_id: list(group[columns_needed].itertuples(index=False, name=None))
            for station_id, group in self.merged.groupby("station_id")
        }
        return self

    def save_to_db(self, db_path: str, run_id: str, label: str = None):
        """
        Persist this run into the shared SQLite database (see db.py
        for the schema), keyed by run_id, instead of a one-off CSV.
        This is what lets multiple simulation runs coexist and be
        compared later, rather than each run overwriting the last.

        Writes:
          - runs             one row describing this run (ess settings, label)
          - battery_results  change / ess_absolute per station per step
          - charging_steps   cleaned SUMO charging rows (for the
                              "energy charged per hour" panel)
          - pv_generation    long-format PV generation (same panel)
          - vehicle_battery  per-vehicle energy consumption, only if
                              battery_path was given to __init__

        Re-running with the same run_id replaces that run's rows
        instead of duplicating them (see db.delete_run).
        """
        from db import get_connection, delete_run

        conn = get_connection(db_path)
        delete_run(conn, run_id)

        conn.execute(
            "INSERT INTO runs (run_id, label, ess_start, ess_max) VALUES (?, ?, ?, ?)",
            (run_id, label or run_id, self.ess, self.ess_max),
        )

        battery_results = self.merged[["station_id", "step_time", "change", "ess_absolute"]].copy()
        battery_results.insert(0, "run_id", run_id)
        battery_results.to_sql("battery_results", conn, if_exists="append", index=False)

        charging_steps = self.stations[["step_time", "chargingStation_id", "step_energyCharged"]].copy()
        charging_steps.insert(0, "run_id", run_id)
        charging_steps.to_sql("charging_steps", conn, if_exists="append", index=False)

        pv_generation = self.pv_long[["station_id", "step_time", "pv_power"]].copy()
        pv_generation.insert(0, "run_id", run_id)
        pv_generation.to_sql("pv_generation", conn, if_exists="append", index=False)

        if self.vehicle_battery is not None:
            vehicle_battery = self.vehicle_battery[
                ["vehicle_id", "timestep_time", "vehicle_totalEnergyConsumed"]
            ].copy()
            vehicle_battery.insert(0, "run_id", run_id)
            vehicle_battery.to_sql("vehicle_battery", conn, if_exists="append", index=False)

        conn.commit()
        conn.close()

    # ---------------------------------------------------------------
    # Orchestration
    # ---------------------------------------------------------------
    def run(self, db_path: str, run_id: str, label: str = None) -> dict:
        """
        Run the full pipeline in order, then persist to the database.
        Each pipeline method returns `self`, so they can be chained.
        Order matters:
            1. load_data            - read raw files
            2. build_pv_long        - reshape PV data
            3. clean_stations       - fix types, fill missing values with 0
            4. bucket_charging_steps - assign each charging step an hourly bucket
            5. merge_and_compute    - join PV + charging, compute "change" (Wh)
            6. calculate_absolute   - turn "change" into running "ess_absolute" (Wh)
            7. build_results        - package into a dict
            8. save_to_db           - persist this run, keyed by run_id
        """
        (
            self.load_data()
            .build_pv_long()
            .clean_stations()
            .bucket_charging_steps()
            .merge_and_compute()
            .calculate_absolute()
            .build_results()
        )
        self.save_to_db(db_path, run_id, label=label)
        return self.results


if __name__ == "__main__":
    load_dotenv()
    latest_timestamp = os.getenv("latest_timestamp")

    pv_path = r"C:\Users\Ralop\Documents\FU Berlin\BeST-eBuS\best-ebus\scenario\eBuS\ext_data\solar_power_v6.csv"
    stations_path = rf"C:\Users\Ralop\Documents\FU Berlin\BeST-eBuS\best-ebus\scenario\sumo\output\electric_bus_{latest_timestamp}_chargingsstations.xml"
    battery_path = rf"C:\Users\Ralop\Documents\FU Berlin\BeST-eBuS\best-ebus\scenario\sumo\output\electric_bus_{latest_timestamp}_battery.xml"
    db_path = r"C:\Users\Ralop\Documents\FU Berlin\BeST-eBuS\best-ebus\scenario\eBuS\files\best_ebus.db"
    run_id = f"run_{latest_timestamp}"

    # 500 kWh starting battery charge, expressed in Wh:
    analysis = ChargingPVAnalysis(pv_path, stations_path, 500000.0, battery_path=battery_path)
    results = analysis.run(db_path=db_path, run_id=run_id)
