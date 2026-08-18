# AI generated on 2026-08-18

from lxml import etree

from energy_storage_system.charging_event import ChargingEvent


class ChargingStation:
    def __init__(self, station_id):
        self.id = station_id
        self.charging_events = []

    def add_event(self, event):
        self.charging_events.append(event)

    @classmethod
    def from_xml(cls, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()

        stations = {}

        for elem in root.iter("chargingEvent"):
            station_id = elem.get("chargingStationId")

            event = ChargingEvent(
                vehicle=elem.get("vehicle"),
                total_energy=float(elem.get("totalEnergyChargedIntoVehicle")),
                begin_sec=float(elem.get("chargingBegin")),
                end_sec=float(elem.get("chargingEnd")),
            )

            if station_id not in stations:
                stations[station_id] = cls(station_id)

            stations[station_id].add_event(event)

        return [
            stations[station_id]
            for station_id in sorted(stations)
        ]