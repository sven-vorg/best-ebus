
USE eBuS.main;

CREATE OR REPLACE TABLE multirun_tripinfo_dedup AS
SELECT
    any_value(tripinfo_arrival) AS tripinfo_arrival,
    any_value(tripinfo_arrivalLane) AS tripinfo_arrivalLane,
    any_value(tripinfo_arrivalPos) AS tripinfo_arrivalPos,
    any_value(tripinfo_arrivalSpeed) AS tripinfo_arrivalSpeed,
    any_value(tripinfo_depart) AS tripinfo_depart,
    any_value(tripinfo_departDelay) AS tripinfo_departDelay,
    any_value(tripinfo_departLane) AS tripinfo_departLane,
    any_value(tripinfo_departPos) AS tripinfo_departPos,
    any_value(tripinfo_departSpeed) AS tripinfo_departSpeed,
    any_value(tripinfo_devices) AS tripinfo_devices,
    any_value(tripinfo_duration) AS tripinfo_duration,
    tripinfo_id,
    any_value(tripinfo_rerouteNo) AS tripinfo_rerouteNo,
    any_value(tripinfo_routeLength) AS tripinfo_routeLength,
    any_value(tripinfo_speedFactor) AS tripinfo_speedFactor,
    any_value(tripinfo_stopTime) AS tripinfo_stopTime,
    any_value(tripinfo_timeLoss) AS tripinfo_timeLoss,
    any_value(tripinfo_vType) AS tripinfo_vType,
    any_value(tripinfo_vaporized) AS tripinfo_vaporized,
    any_value(tripinfo_waitingCount) AS tripinfo_waitingCount,
    any_value(tripinfo_waitingTime) AS tripinfo_waitingTime,

    any_value(emissions_CO2_abs) AS emissions_CO2_abs,
    any_value(emissions_CO_abs) AS emissions_CO_abs,
    any_value(emissions_HC_abs) AS emissions_HC_abs,
    any_value(emissions_NOx_abs) AS emissions_NOx_abs,
    any_value(emissions_PMx_abs) AS emissions_PMx_abs,
    any_value(emissions_electricity_abs) AS emissions_electricity_abs,
    any_value(emissions_fuel_abs) AS emissions_fuel_abs,

    any_value(battery_actualBatteryCapacity) AS battery_actualBatteryCapacity,
    any_value(battery_depleted) AS battery_depleted,
    any_value(battery_totalEnergyConsumed) AS battery_totalEnergyConsumed,
    any_value(battery_totalEnergyRegenerated) AS battery_totalEnergyRegenerated,

    scenario,
    seed
FROM multirun_tripinfo
GROUP BY scenario, seed, tripinfo_id;

SELECT count(*) FROM multirun_tripinfo;
SELECT count(*) FROM multirun_tripinfo_dedup;