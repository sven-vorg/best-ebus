# ReadMe for the eBus extension to the BeST-Scenario

The **electric Bus utilization Scenario (eBuS)** is a fork of the **[Berlin Sumo Traffic (BeST) Scenario.](https://github.com/mosaic-addons/best-scenario)**
It is being developed as part of a masters-thesis at the FU-Berlin in 2026.
Its goal is extending the capabilitys of BeST to simulate electric buses and their charging stations to generate data on charging behaviour and energy requierments.
Additionaly skripts for extending charging stations into integrated energy hubs, using energy storage systems and photovoltaic power generation, are planned.

The simulation is intended to be able to handle multiple depots, service lines, charging stations and bus models.

To limit the scope during the development and the proof-of-concept phase, the implementation focuses on two depots, each designed for 200+ buses, servicing 49 lines and implementing 94 charging Stations.

Dependencys:
* [Eclipse Sumo (Version 1.27.0)](https://github.com/eclipse-sumo/sumo/tree/main/docs)
* An electric Vehicle Scheduling Problem (eVSP) solving methode for a baseline solution
* Online connectivity for [PVGIS-API](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en) calls

## Instructions
All skripts and files for the simulation in sumo are saved within the eBuS directory.
A

### Order of Operations for the skripts in the skript directory


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