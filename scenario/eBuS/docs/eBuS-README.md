# ReadMe for the eBuS extension to the BeST-Scenario

The **electric Bus utilization Scenario (eBuS)** is a fork of the **[Berlin Sumo Traffic (BeST) Scenario.](https://github.com/mosaic-addons/best-scenario)**
It is being developed as part of a masters-thesis at the FU-Berlin in 2026 with the goal of extending the capabilitys of BeST to simulate electric buses and their charging stations to generate data on charging behaviour and energy requierments.
Additionaly skripts for extending charging stations into integrated energy hubs, using energy storage systems and photovoltaic power generation, are planned.

The simulation is intended to be able to handle multiple depots, service lines, charging stations and bus models.

To limit the scope during the development and the proof-of-concept phase, the implementation focuses on two depots, each designed for 200+ buses, servicing 49 lines and implementing 94 charging Stations.

Dependencys:
* [Eclipse Sumo (Version 1.27.0)](https://github.com/eclipse-sumo/sumo/tree/main/docs)
* An electric Vehicle Scheduling Problem (eVSP) solving methode for a baseline solution
* Online connectivity for [PVGIS-API](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en) calls

## Modifications
Minor adjustments have been made to *berlin.net.xml*, to include two bus depots, one at **Cicerostraße** in Charlottenburg-Wilmersdorf, and the other at **Müllerstraße**, Wedding. Within the code these are named cicerostrasse and muellerstrasse respectively.
Additionaly whenever changes to intersections or lanes where made, these had to be mirrored by adapting the *berlin_bus.rou.xml* accordingly.

## Instructions
All skripts and files for the simulation in sumo are saved within the eBuS directory.
Manual defintion of 
Files in *preprocessing* create textfiles used as input for solving heuristic. 

### Order of Operations for the skripts in the skript directory

#### Heuristic Preprocessing
1. Defining depots and belonging service lines.
Assumes a csv file with the header: *depot,line,type*.
Available lines are taken from *berlin_bus.rou.xml*, where there is a *to* and *from* for each.
2. *heuristic_preprocessing.py* is a wrapper for all other skripts in the *preprocessing* directory, performing the functions calls in order.
3. Begining with *filter_lines.py* where first every route and flow not found in the *depot_line_type.csv" is removed from *berlin_bus.rou.xml*.
While **BeST** operates on the **SUMO** flow-functionality, which generates and destroys vehicles for a given route periodically, **eBuS** requieres the use of persistent vehicles. Therefore different parameters are calculated from the combined routes and flows of each line. 
This operation creates a *to* and *from* for each route, and calculates the number of requiered repetitions and period intevals from the corresponding flows. The result is a *merged_routes.csv* which in turn can be used to create trip defintions for each depot.
4. As there was an issue, with routes continuing beyond their last passenger stations, to travel to operational stations, *cut_lines.py* removes these sections of routes. While it would be more accurate to also model operation stations as charging-points, this simplification was made for time expenditure reasons.
5. The calculation of deadheads, e.g. trips without passengers between service stations, is requiered to build the complete tour of a singel vehicle. The skript produces not only information on the travel time between every stop of the network, but also creates a reference *.rou.xml* from which all later routes are constructed. Deadhead timings are also exportet as *.txt* to be used as solver input.

#### Heuristic Postprocessing

0. Assumes solver output with a specific format. \
    One *solution.json* for each depot. This includes all vehicles and the trips they perform, aswell as designated charging stations and times.
1. Designated charging station ids are read from the solution, corresponding busStops are read from *berlin_bus_stops.add.xml* and modfied into charging stations at the same position. Chargers at the depots are added. Here modifcations to charging station parameters can be made. For future functionality geo coordinates are calculated and saved.
2. *pv_for_station.py* is a work in progress, photovoltaic power generation for charging stations is requested from PVGIS via API calls. Offline functionality could be a future goal.
3. The building of the final routes concatenates the building blocks from the reference route file accoarding to the solution. To handle differing departure times, vehicles and routes are split into two *e_vehicles.rou.xml* and *e_routes.rou.xml. This way timing values in the later are automatically relative to the departure time of the vehicles.

### Depots and Vehicle Types

*e_depots.add.xml* and *e_type.add.xml*.
These short files are manually created, and define TAZ zones for both depots, as well as available vehicle types to perform the routes. Currently one electric bus is available, testing with more will soon be possible.

### Sumo Config File

**eBuS** comes with its own **SUMO** configuration file, *e_berlin.sumocfg*. This config loads all previously created *e_* files and sets the simula
tion parameters. Additional output requierments are set, creating logs for charging and battery output.

## ToDos
* *split filter_lines.py* into a file responsible for filtering, and a file responsible for providing heuristic input
* Integrate *cut_lines.py* into filtering
* Integrate old *gtfs_worker.ipynb* into heuristic input skript
* Take charging time from *solution* file
* Add more vehicle types and implement type choice dependet upon *depot_line_type.csv*

## Information & Contact
**Author:** Sven Vorgheim \
**License:** \
**Maintainer:** Sven Vorgheim \
**Email:** sven.vorgheim@fu-berlin.de \
**Project status:** Prototype \
**Last updated:** 10.07.2026

### Disclaimer 
Generative AI was used in the creation process for some skripts.