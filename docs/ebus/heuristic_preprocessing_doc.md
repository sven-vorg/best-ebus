# Scenario/preprocessing
Skripts in *preprocessing* are used to create textfiles used as input for a solving heuristic. 
The six scrips are introduced in order of operations.

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
This is a very simple skript, which only needs to be run whenever new bus stop is added to the scenario defintion.
The *coordinate_calculator* takes a .net.xml file and a .add.xml file containing **bus stops** and uses the function **positionAtShapeOffset** provided by sumolib to calculate the real world coordinates, which are then added to the stops under the **coordinate** attribute.

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
The *filter_lines* skript copys a .rou.xml file and removes every route and flow not found in the *[heuristic_preprocessing.lines]* table of *ebus_config.toml*. Additionaly an .add.xml file with the stops corresponding to the routes is read, to get humand readable names of departure and arrival station. This operation creates a *to* and *from* for each route, and calculates the number of requiered repetitions and period intevals from the corresponding flows. These parameters gathered from the .xml files are then combined into a *trips.txt* file routes and flows of each line. 

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
It performs the definition of depots and belonging service lines. For that it assumes a *[heuristic_preprocessing.lines]* table in *ebus_config.toml*, mapping each line to its depot and vehicle type. \
Available lines are taken from *berlin_bus.rou.xml*, where there is a *to* and *from* for each.
For eBuS this data has been taken from the website [berliner-lininchronik.de](https://www.berliner-linienchronik.de/fahrzeuge-bvg.html) (Sawall, Fabian; 2026) \
While manual definition of routes is possible, and adjustments can be made to fine-tune simulation behaviour, the assignment of vehciles to services is computed by a heuristic solving method (Janus, Robert; n.y.)

While **BeST** operates on the **SUMO** flow-functionality, which generates and destroys vehicles for a given route periodically, **eBuS** requieres the use of persistent vehicles.




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