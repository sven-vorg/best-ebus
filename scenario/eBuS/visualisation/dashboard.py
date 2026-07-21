import altair as alt
import streamlit as st
from pathlib import Path

from database.db_connector import get_connection, list_runs

# Solar power table (solar_power_v6) is stored wide: one column per hour-end
# second of the day ("3600", "7200", ..., "86400"). We unpivot it to compute
# totals per hour. Column "3600" == hour 0 (00:00-01:00), "7200" == hour 1, etc.
SOLAR_HOUR_SECONDS = list(range(3600, 86400 + 1, 3600))

# Day for which the day-ahead price lookup is done (07.12.2023).
PRICE_DATE = "2023-12-07"


class Dashboard:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = get_connection(db_path)
        self._build_surface()
        #self._show_vehicle_stats()
        self._plot_consumed_energy_per_hour()
        self._plot_charged_generated_price_per_hour()
        self._plot_solar_value_vs_charging_cost()

    def _build_surface(self):
        st.title("eBuS Visualisation")
        # Dropdown
        selected_id = st.selectbox(
            "Select a sumo run",
            options=list_runs(self.conn),
        )

    def _show_vehicle_stats(self):
        # Get all keys
        ids = self.conn.execute(
            "SELECT trip_id FROM fact_trip ORDER BY trip_id").fetchdf()["trip_id"].tolist()

        # Dropdown
        selected_id = st.selectbox(
            "Select a vehicle",
            options=ids,
        )

        # Query selected row from battery
        if selected_id is not None:
            df = self.conn.execute(
                """
                SELECT *
                FROM battery
                WHERE vehicle_id = ?
                """,
                [selected_id],
            ).fetchdf()

            st.line_chart(
                df,
                x="timestep_time",
                y=["vehicle_energyCharged",
                   "vehicle_energyConsumed",
                   "vehicle_totalEnergyRegenerated",
                   "vehicle_totalEnergyConsumed"]
            )

        def other():
            # Query selected row from fact_trip
            if selected_id is not None:
                df = self.conn.execute(
                    """
                    SELECT *
                    FROM fact_trip
                    WHERE trip_id = ?
                    """,
                    [selected_id],
                ).fetchdf()

                st.line_chart(df)
                pass

    def _plot_consumed_energy_per_hour(self):
        """Plot 1: Kumulierter verbrauchter Strom pro Stunde.

        Summiert vehicle_energyConsumed aus 'battery' je Stunden-Bucket
        (0-3600s, 3601-7200s, ...).
        """
        st.subheader("Kumulierter verbrauchter Strom pro Stunde")

        conn = get_connection(self.db_path)
        try:
            df = conn.execute(
                """
                SELECT
                    CAST(FLOOR(CAST(timestep_time AS DOUBLE) / 3600) AS BIGINT) AS hour,
                    SUM("vehicle_energyConsumed") AS energy_consumed_wh
                FROM battery
                GROUP BY hour
                ORDER BY hour
                """
            ).fetchdf()
        finally:
            conn.close()

        if df.empty:
            st.info("Keine Daten für diesen Plot verfügbar.")
            return

        st.bar_chart(df, x="hour", y="energy_consumed_wh")

    def _plot_charged_generated_price_per_hour(self):
        """Plot 2: Geladene Energie, generierte Energie und Strompreis pro Stunde.

        - Geladene Energie: SUM(step_energyCharged) aus 'chargingstations', je Stunde.
        - Generierte Energie: SUM aller Ladestationen aus 'solar_power_v6', je Stunde.
        - Preis: day_ahead_prices_long, price_eur_per_mwh / 1_000_000 (=> EUR/Wh),
          für PRICE_DATE, je hour_of_day.
        """
        st.subheader("Geladene / generierte Energie und Strompreis pro Stunde")

        conn = get_connection(self.db_path)
        try:
            charged_df = conn.execute(
                """
                SELECT
                    CAST(FLOOR(CAST(step_time AS DOUBLE) / 3600) AS BIGINT) AS hour,
                    SUM("step_energyCharged") AS energy_charged_wh
                FROM chargingstations
                GROUP BY hour
                ORDER BY hour
                """
            ).fetchdf()

            solar_columns = ", ".join(f'"{s}"' for s in SOLAR_HOUR_SECONDS)
            generated_df = conn.execute(
                f"""
                SELECT
                    CAST(second_label AS BIGINT) / 3600 - 1 AS hour,
                    SUM(generated_power) AS energy_generated_wh
                FROM (
                    UNPIVOT solar_power_v6
                    ON {solar_columns}
                    INTO NAME second_label VALUE generated_power
                )
                GROUP BY hour
                ORDER BY hour
                """
            ).fetchdf()

            price_df = conn.execute(
                """
                SELECT
                    hour_of_day AS hour,
                    price_eur_per_mwh / 1000000.0 AS price_eur_per_wh
                FROM day_ahead_prices_long
                WHERE "date" = CAST(? AS DATE)
                AND zone = 'Germany/Luxembourg'
                ORDER BY hour_of_day
                """,
                [PRICE_DATE],
            ).fetchdf()
        finally:
            conn.close()

        # Force a consistent integer join key - a float/int dtype mismatch
        # between the three queries can silently drop matches on merge.
        for frame in (charged_df, generated_df, price_df):
            frame["hour"] = frame["hour"].astype("Int64")

        if price_df.empty:
            st.warning(
                f"Keine Preisdaten für {PRICE_DATE} gefunden - bitte prüfen, "
                "ob dieses Datum in day_ahead_prices_long vorhanden ist."
            )

        merged = (
            charged_df.merge(generated_df, on="hour", how="outer")
            .merge(price_df, on="hour", how="outer")
            .sort_values("hour")
        )
        # Zero-fill only the energy columns. Leave price_eur_per_wh as NaN
        # when missing, so a real gap in the price data stays visible
        # instead of silently rendering as 0.
        merged[["energy_charged_wh", "energy_generated_wh"]] = merged[
            ["energy_charged_wh", "energy_generated_wh"]
        ].fillna(0)

        if merged.empty:
            st.info("Keine Daten für diesen Plot verfügbar.")
            return

        base = alt.Chart(merged).encode(x=alt.X("hour:O", title="Stunde"))

        energy_chart = (
            base.transform_fold(
                ["energy_charged_wh", "energy_generated_wh"],
                as_=["Energie-Typ", "Wert"],
            )
            .mark_line(point=True)
            .encode(
                y=alt.Y("Wert:Q", title="Energie [Wh]"),
                color=alt.Color("Energie-Typ:N", title=""),
            )
        )

        price_chart = base.mark_line(point=True, strokeDash=[4, 2], color="red").encode(
            y=alt.Y("price_eur_per_wh:Q", title="Preis [EUR/Wh]", axis=alt.Axis(titleColor="red")),
        )

        combined = alt.layer(energy_chart, price_chart).resolve_scale(y="independent")
        st.altair_chart(combined, use_container_width=True)

    def _plot_solar_value_vs_charging_cost(self):
        """Plot 3: Wert der generierten Solarenergie vs. Kosten der Ladestationen, je Stunde.

        - Wert generierter Energie = generierte Energie[Wh] * Preis[EUR/Wh].
        - Kosten Ladestationen = an Fahrzeuge geladene Energie[Wh] * Preis[EUR/Wh]
          (Annahme: die geladene Energie wird zum jeweiligen Day-Ahead-Preis bewertet).
        """
        st.subheader("Wert generierter Solarenergie vs. Kosten Ladestationen pro Stunde")

        conn = get_connection(self.db_path)
        try:
            charged_df = conn.execute(
                """
                SELECT
                    CAST(FLOOR(CAST(step_time AS DOUBLE) / 3600) AS BIGINT) AS hour,
                    SUM("step_energyCharged") AS energy_charged_wh
                FROM chargingstations
                GROUP BY hour
                ORDER BY hour
                """
            ).fetchdf()

            solar_columns = ", ".join(f'"{s}"' for s in SOLAR_HOUR_SECONDS)
            generated_df = conn.execute(
                f"""
                SELECT
                    CAST(second_label AS BIGINT) / 3600 - 1 AS hour,
                    SUM(generated_power) AS energy_generated_wh
                FROM (
                    UNPIVOT solar_power_v6
                    ON {solar_columns}
                    INTO NAME second_label VALUE generated_power
                )
                GROUP BY hour
                ORDER BY hour
                """
            ).fetchdf()

            price_df = conn.execute(
                """
                SELECT
                    hour_of_day AS hour,
                    price_eur_per_mwh / 1000000.0 AS price_eur_per_wh
                FROM day_ahead_prices_long
                WHERE "date" = CAST(? AS DATE)
                AND zone = 'Germany/Luxembourg'
                ORDER BY hour_of_day
                """,
                [PRICE_DATE],
            ).fetchdf()
        finally:
            conn.close()

        for frame in (charged_df, generated_df, price_df):
            frame["hour"] = frame["hour"].astype("Int64")

        if price_df.empty:
            st.warning(
                f"Keine Preisdaten für {PRICE_DATE} gefunden - bitte prüfen, "
                "ob dieses Datum in day_ahead_prices_long vorhanden ist."
            )

        merged = (
            generated_df.merge(charged_df, on="hour", how="outer")
            .merge(price_df, on="hour", how="outer")
            .sort_values("hour")
        )
        merged[["energy_generated_wh", "energy_charged_wh"]] = merged[
            ["energy_generated_wh", "energy_charged_wh"]
        ].fillna(0)

        if merged.empty:
            st.info("Keine Daten für diesen Plot verfügbar.")
            return

        merged["wert_generierte_energie_eur"] = (
            merged["energy_generated_wh"] * merged["price_eur_per_wh"]
        )
        merged["kosten_ladestationen_eur"] = (
            merged["energy_charged_wh"] * merged["price_eur_per_wh"]
        )

        st.line_chart(
            merged,
            x="hour",
            y=["wert_generierte_energie_eur", "kosten_ladestationen_eur"],
        )