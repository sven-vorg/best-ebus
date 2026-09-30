# Scenario/preprocessing
Scripts in *preprocessing* are used to create text files used as input for a solving heuristic. 
The six scripts are introduced in order of operations.

```mermaid
flowchart TB
    n1("scenario/"):::root
        n2("eBuS/"):::folder
        n1 --> n2
        n29("preprocessing/"):::folder
        n2 --> n29
        n30["coordinate_calculator.py"]:::py
        n29 --> n30
        n33["filter_lines.py"]:::py
        n29 --> n33
        n35["termination_points.py"]:::py
        n29 --> n35
        n31["cut_lines.py"]:::py
        n29 --> n31
        n32["deadhead_calculator.py"]:::py
        n29 --> n32
        n34["heuristic_preprocessing.py"]:::py
        n29 --> n34
    classDef root fill:#d9e8ff,stroke:#3b6fb6,color:#111,font-weight:bold
    classDef folder fill:#eef3f8,stroke:#7a8ea6,color:#222
    classDef py fill:#e6f4e6,stroke:#4d9a4d,color:#222
    classDef data fill:#fff4d6,stroke:#c99a2e,color:#222
```

## Coordinate Calculator
This is a very simple script, which only needs to be run whenever a new bus stop is added to the scenario definition.
The *coordinate_calculator* takes a .net.xml file and a .add.xml file containing **bus stops** and uses the function **positionAtShapeOffset** provided by sumolib to calculate the real-world coordinates, which are then added to the stops under the **coordinate** attribute.

```mermaid
classDiagram
    class c_scenario_eBuS_preprocessing_coordinate_calculator_CoordinateCalculator["CoordinateCalculator"] {
        +net_file_path
        +bus_stops_file_path
        +net
        +bus_stops_tree
        +bus_stops_root
        +__init__(net_file_path, bus_stops_file_path)
        +add_coordinates_to_bus_stops()
        +save(output_path)
    }
```

## Filter Lines
The *filter_lines* script creates a copy of the .rou.xml file and removes every route and flow not found in the *[heuristic_preprocessing.lines]* table of *ebus_config.toml*. Additionally, an .add.xml file with the stops corresponding to the routes is read to get human-readable names of departure and arrival stations. This operation creates a *to* and *from* for each route and calculates the number of required repetitions and period intervals from the corresponding flows. These parameters gathered from the .xml files are then combined into a *trips.txt* file from routes and flows of each line. 

```mermaid
classDiagram
    class c_scenario_eBuS_preprocessing_filter_lines_FilterLines["FilterLines"] {
        +routes_tree
        +routes_root
        +selected_lines
        +lines
        +bus_stops_tree
        +bus_stops_root
        +output_dir
        +route_calculations
        +__init__(routes_file, selected_lines, bus_stops_file, output_dir)
        +extract_flow_information()
        +routes_to_trips(create_csv)
        +main()
        +parse_time(t)
        +stop_name_dict()
        +stop_coord_dict()
    }
```

## Cut Lines

The *cut_lines* script again is very simple and does as its name suggests. It cuts all edges before the first occurrence of the departure station and after the last occurrence of the arrival station. This is necessary as buses may perform undesired circling back operations, drive to unmarked waiting spots, or perform a simulation exiting route in the original GTFS data used by BeSt.

```mermaid
classDiagram
    class c_scenario_eBuS_preprocessing_cut_lines_CutLines["CutLines"] {
        +stations_path
        +routes_root
        +stations_root
        +__init__(stations_path, routes_root)
        +trim_routes()
        +write_to_xml(output_path)
    }
```

## Deadhead Calculator
The *deadhead_calculator* picks up where the routes were left after cutting and filtering, calculating the timings between all possible termination points based upon the used network itself, and appends these to the route file. They are named using the following format: "route{FromStopId}_{ToStopId}".

```mermaid
classDiagram
    class c_scenario_eBuS_preprocessing_deadhead_calculator_DeadheadCalculator["DeadheadCalculator"] {
        +net
        +routes_root
        +station_root
        +termination_points
        +depots
        +output
        +__init__(network, stations, routes_root, termination_points, depots, output)
        +calculate_station_deadheads()
    }
```

## Heuristic Preprocessing
*heuristic_preprocessing.py* is a wrapper for all other scripts in the *preprocessing* directory, performing the functions calls in order.

```mermaid
classDiagram
    direction TB
    class c_scenario_eBuS_preprocessing_heuristic_preprocessing_HeuristicPreprocessing["HeuristicPreprocessing"] {
        +routes_file
        +stations_file
        +network_file
        +selected_lines
        +termination_points
        +depots
        +output_dir
        +__init__(routes_file, stations_file, network_file, selected_lines, termination_points, depots, output_dir)
        +main()
    }
```

Next Chapter [Scenario/postprocessing](./postprocessing_doc.md).
