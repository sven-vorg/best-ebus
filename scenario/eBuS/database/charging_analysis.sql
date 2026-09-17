
SELECT
    scenario,
    seed,
    SUM(chargingEvent_totalEnergyChargedIntoVehicle) AS total_energy_charged
FROM main.multirun_chargingstations
WHERE chargingEvent_chargingStationId NOT LIKE 'cd\_%' ESCAPE '\'
  AND scenario = 'summer'
  AND seed = 65
GROUP BY scenario, seed;

WITH run_totals AS (
    SELECT
        scenario,
        seed,
        SUM(chargingEvent_totalEnergyChargedIntoVehicle) AS total_energy_charged
    FROM main.multirun_chargingstations
    WHERE chargingEvent_chargingStationId NOT LIKE 'cd\_%' ESCAPE '\'
    GROUP BY scenario, seed
)
SELECT
    scenario,
    COUNT(*) AS number_of_runs,
    AVG(total_energy_charged) AS mean,
    STDDEV_SAMP(total_energy_charged) AS std,
    MIN(total_energy_charged) AS min,
    MAX(total_energy_charged) AS max
FROM run_totals
GROUP BY scenario
ORDER BY scenario;

-- AI generated on 2026-09-08
WITH bus_daily_energy AS (
    SELECT
        scenario,
        seed,
        chargingEvent_vehicle AS bus_id,
        SUM(chargingEvent_totalEnergyChargedIntoVehicle) AS daily_energy_charged
    FROM main.multirun_chargingstations
    WHERE chargingEvent_chargingStationId NOT LIKE 'cd\_%' ESCAPE '\'
    GROUP BY
        scenario,
        seed,
        chargingEvent_vehicle
)

SELECT
    scenario,
    seed,
    ROUND(AVG(daily_energy_charged), 2) AS avg_energy_per_bus,
    ROUND(MIN(daily_energy_charged), 2) AS min_energy_per_bus,
    ROUND(MAX(daily_energy_charged), 2) AS max_energy_per_bus
FROM bus_daily_energy
GROUP BY
    scenario,
    seed
ORDER BY
    scenario,
    seed;


SELECT
    *
    FROM main.multirun_tripinfo
    WHERE depleted = 1


SELECT * 
    FROM "eBuS - Kopie"."main"."multirun_stopinfo"
    WHERE stopinfo_id = 'bus_3066'
    AND scenario = 'summer'
    AND seed = '67'
    ORDER BY stopinfo_started


SELECT * FROM "eBuS - Kopie"."main"."multirun_tripinfo"
    WHERE tripinfo_id = 'bus_3066'
    AND scenario = 'summer'
    AND seed = '67'
