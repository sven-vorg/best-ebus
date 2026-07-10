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
1. Defining depots and belonging service lines.  \
Assumes a csv file with the header: *depot,line,type*. \
Available lines are taken from *berlin_bus.rou.xml*, where there is a *to* and *from* for each.
2. *heuristic_preprocessing.py* is a wrapper for all other skripts in the *preprocessing* directory, performing the functions calls in order.
3. Begining with *filter_lines.py* where first every route and flow not found in the *depot_line_type.csv" is removed from *berlin_bus.rou.xml*.
While **BeST** operates on the **SUMO** flow-functionality, which generates and destroys vehciles for a given route periodically, eBuS requieres the use of persistent vehicles. Therefore different parameters are calculated from the combined routes and flows of each line. 


            "route": route_id,
            "start_stop_id": start_stop_id,
            "end_stop_id": end_stop_id,
            "flow_begin": flow_begin,
            "flow_end": flow_end,
            "period": period,
            "duration": duration,
            "nr_of_buses": math.ceil(duration / period),
            "nr_of_repetitions": int((flow_end - flow_begin) / duration),
            "nr_of_trips_pd": int((flow_end - flow_begin) / period),
        }

Solution format: 
## Information & Contact
**Author:** Sven Vorgheim \
**License:** \
**Maintainer:** Sven Vorgheim \
**Email:** sven.vorgheim@fu-berlin.de \
**Project status:** Prototype \
**Last updated:** 10.07.2026

### Disclaimer 
Generative AI was used in the creation process for some skripts.