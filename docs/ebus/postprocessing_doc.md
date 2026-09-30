# Scenario/postprocessing

Scripts in *postprocessing* take a solution in a specific format to then build fully realised vehicles and their routes from the previously defined trips.

```mermaid
flowchart TB
    n0("best-ebus/"):::root
    n1("scenario/"):::folder
    n0 --> n1
    n2("eBuS/"):::folder
    n1 --> n2
    n24("postprocessing/"):::folder
    n2 --> n24
    n25["build_routes.py"]:::py
    n24 --> n25
    n26["build_vehicles.py"]:::py
    n24 --> n26
    n27["charging_stations.py"]:::py
    n24 --> n27
    n28["heuristic_postprocessing.py"]:::py
    n24 --> n28
    classDef root fill:#d9e8ff,stroke:#3b6fb6,color:#111,font-weight:bold
    classDef folder fill:#eef3f8,stroke:#7a8ea6,color:#222
    classDef py fill:#e6f4e6,stroke:#4d9a4d,color:#222
    classDef data fill:#fff4d6,stroke:#c99a2e,color:#222

```


# Charging Stations

The *charging_stations.py* reads designated charging station IDs from the solution, corresponding bus stops are read from *berlin_bus_stops.add.xml* and modified into charging stations at the same position. Chargers at the depots are added. Here modifications to charging station parameters can be made. For future functionality geo coordinates are calculated and saved.

```mermaid
classDiagram
    class c_scenario_eBuS_postprocessing_charging_stations_ChargingStations["ChargingStations"] {
        +net
        +STATION_ROOT
        +ROUTE_ROOT
        +OUTPUT_PATH
        +AREA_LOOKUP
        +SOLUTION
        +station_id_mapping
        +POWER
        ... +4 attributes
        +__init__(net, station_root, route_root, output_path, area_path, solution_path, station_id_path, power, total_power_factor, allow_depot_charging, depot_total_power_factor, inactive_list)
        +station_id_lookup(station_id_mapping_path) dict
        +area_lookup(area_df)
        +charging_stations_from_solution()
        +main()
    }
```

## Build Vehicles
The *build_vehicles.py* script is the first step of creating the desired buses in the form utilized by sumo. The number, type and depot affiliation is determined by the solution file. A vehicle is build according to the definition from SUMO. Ids in the format "bus_{id from solution}" need to be unique. The type, needs to either be a SUMO default, or taken from additionally defined vehicles types. In this case it determines the exact type of vehicle used, data on line-type association is taken from [berliner-lininchronik.de](https://www.berliner-linienchronik.de/fahrzeuge-bvg.html) (Sawall, Fabian; 2026).

```mermaid
classDiagram
    class c_scenario_eBuS_postprocessing_build_vehicles_BuildVehicles["BuildVehicles"] {
        +SOLUTION_PATH
        +VEHICLES_OUTPUT
        +SOC_PERCENTAGE
        +OFFSET
        +DEPOTS
        +dict~Any Any~ trip_to_start
        +dict~Any Any~ trip_to_end
        +dict~Any Any~ trip_to_depart
        ... +2 attributes
        +__init__(solution_path, vehicles_output, soc_percentage, tripp_dict, deadhead_path, offset)
        +main()
        +calculate_departure(bus, offset) int
        +run_sort_routes(root) None
    }
```

## Build Routes

The creation of routes in *build_routes.py* is a centerpiece of the scenario preparation. The script reads the solution, and stitches the route from the individual trips, adjusting stops, cutting duplicate edges and stops while adding charging events and depot departure and arrival.

```mermaid
classDiagram
    class c_scenario_eBuS_postprocessing_build_routes_BuildRoutes["BuildRoutes"] {
        +solution_dict
        +station_id_dict
        +trips_df
        +original_routes
        +deadhead_timings
        +output_path
        +offset
        +__init__(solution_path, station_id_map_path, trips_path, routes_path, deadhead_timing_path, output_path, despawn_offset)
        +main()
        +build_deadheads(last_stop, first_stop)
        +remove_duplicate_edges(edges)
        +remove_duplicate_stops(stops)
        +build_depot_deadheads(bus, first_stop, last_stop)
        +old_build_stops(trip, original_trip_id, route_id, charging_events)
        +build_stops(trip, original_trip_id, route_id, charging_events)
        ... +4 methods
    }
```

## Heuristic Postprocessing
*heuristic_preprocessing.py* is a wrapper for all other scripts in the *preprocessing* directory, performing the functions calls in order.

```mermaid
classDiagram
    class c_scenario_eBuS_postprocessing_heuristic_postprocessing_HeuristicPostprocessing["HeuristicPostprocessing"] {
        +net
        +station_root
        +route_root
        +output_path
        +area_path
        +input_path
        +input_dict
        +deadhead_path
        ... +12 attributes
        +__init__(net, station_root, route_root, output_path, area_path, input_path, input_dict, deadhead_path, soc_percentage, merged_routes, merged_routes_output, vehicles_output, station_id_path, chargingstation_power, total_power_factor, offset, despawn_offset, allow_depot_charging, depot_total_power_factor, inactive_list)
        +main()
    }
```

Next Chapter [Scenario/ebus_main](./ebus_main_doc.md).
