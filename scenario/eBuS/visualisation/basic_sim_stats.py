from database import db_connector
import streamlit as st

class BasicSimStats():
    def __init__(self) -> None:
        pass

    @staticmethod
    def basic_stats_table(run_id, db_path):
        """
        Display basic simulation statistics.
        """
        st.subheader("Basic Simulation Facts")

        conn = db_connector.get_connection(db_path)
        try:
            df = conn.execute(
                """
                SELECT
                    COUNT(tripinfo_id) AS trips,
                    SUM(tripinfo_routeLength) / 1000.0 AS total_km,
                    SUM(battery_totalEnergyConsumed) AS total_energy_consumed,
                    SUM(CASE WHEN battery_depleted = 'true' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN tripinfo_vaporized = 'true' THEN 1 ELSE 0 END)
                FROM tripinfo
                WHERE simulation_timestamp = ?
                """,
                [run_id],
            ).fetchdf()
        finally:
            conn.close()

        if df.empty:
            st.info("No data available.")
            return

        st.table(df)