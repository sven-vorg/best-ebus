from pathlib import Path

import matplotlib.pyplot as plt
import geopandas as gpd
import contextily as cx
from lxml import etree

# The basemap image barely changes between runs, so tiles are downloaded
# once and cached here instead of being re-fetched from the web every time.
BASEMAP_CACHE_DIR = Path(__file__).resolve().parent.parent / "files" / "basemaps"

# OpenStreetMap's tile server enforces a strict usage policy (identifying
# User-Agent required, no anonymous/bulk downloading) and will 403 requests
# it flags as automated. We only ever hit the network here once per
# cache_name, so it's fine to identify ourselves and back off/retry
# generously instead of failing fast.
_TILE_HEADERS = {
    "User-Agent": "BeSTeBuS-eBuS-analysis-script/1.0 (academic thesis project, one-off basemap download)",
}


def _add_cached_basemap(ax, cache_name, source=cx.providers.OpenStreetMap.Mapnik, zoom="auto"):
    BASEMAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = BASEMAP_CACHE_DIR / f"{cache_name}.tif"

    if not cache_path.exists():
        west, east, south, north = ax.axis()
        cx.bounds2raster(
            west, south, east, north,
            path=str(cache_path), zoom=zoom, source=source,
            headers=_TILE_HEADERS, wait=15, max_retries=8,
        )

    cx.add_basemap(ax, source=str(cache_path))


class ChargingStationMap:

    def __init__(self, stations_path: Path, chargingstations_path: Path | None = None, ess_path: Path | None = None):
        self.stations = self.parse_stations(stations_path)
        self.energy_by_station = (
            self.parse_charging_events(chargingstations_path) if chargingstations_path else {}
        )
        self.pv_by_station = (
            self.parse_pv_generation(ess_path) if ess_path else {}
        )
        self.pv_curtailed_by_station = (
            self.parse_pv_curtailment(ess_path) if ess_path else {}
        )

    def parse_stations(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        stations = {}

        for elem in root.iter('chargingStation'):
            coords = elem.get('coordinates')
            if coords is None:
                continue
            lon, lat = (float(v) for v in coords.split(','))
            stations[elem.get('id')] = {
                'name': elem.get('name').replace('_charger', ''),
                'lon': lon,
                'lat': lat,
            }

        return stations

    def parse_charging_events(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        energy_by_station = {}

        for elem in root.iter('chargingEvent'):
            station_id = elem.get('chargingStationId')
            energy = float(elem.get('totalEnergyChargedIntoVehicle'))
            energy_by_station[station_id] = (
                energy_by_station.get(station_id, 0.0) + energy
            )

        return energy_by_station

    def parse_pv_curtailment(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        pv_by_station = {}

        for station in root.iter('station'):
            station_id = station.get('id')
            pv_curtailed = float(station.get('pvCurtailed'))
            pv_by_station[station_id] = (
                pv_by_station.get(station_id, 0.0) + pv_curtailed /1000
            )

        return pv_by_station

    def parse_pv_generation(self, xml_path):
        tree = etree.parse(xml_path)
        root = tree.getroot()
        pv_by_station = {}

        for station in root.iter('station'):
            station_id = station.get('id')
            pv_generated = float(station.get('pvGenerated'))
            pv_by_station[station_id] = (
                pv_by_station.get(station_id, 0.0) + pv_generated /1000
            )

        return pv_by_station

    def plot_energy_map(self, save_path=None, min_size=20, max_size=2000):
        """
        Map of Berlin with a circle per charging station, sized by the
        total energy charged into vehicles at that station over the day.
        """
        self._plot_station_map(
            values_by_station={
                station_id: energy_wh / 1000
                for station_id, energy_wh in self.energy_by_station.items()
            },
            unit_label="kWh",
            title="Total energy charged per charging station",
            color='#F8CECC',
            edgecolor='#B85450',
            save_path=save_path,
            min_size=min_size,
            max_size=max_size,
            cache_name="energy_map",
        )

    def plot_pv_generation_map(self, save_path=None, min_size=20, max_size=2000):
        """
        Map of Berlin with a circle per charging station, sized by the
        total PV energy generated at that station over the day.
        """
        self._plot_station_map(
            values_by_station=self.pv_by_station,
            unit_label="kWh",
            title="Total PV energy generated per charging station",
            color='#FFF2CC',
            edgecolor='#D6B656',
            save_path=save_path,
            min_size=min_size,
            max_size=max_size,
            cache_name="pv_generation_map",
        )

    def plot_pv_curtailment_map(self, save_path=None, min_size=20, max_size=2000):
        """
        Map of Berlin with a circle per charging station, sized by the
        total PV energy curtailed at that station over the day.
        """
        self._plot_station_map(
            values_by_station=self.pv_curtailed_by_station,
            unit_label="kWh",
            title="Total PV energy curtailed per charging station",
            color='#E1D5E7',
            edgecolor='#9673A6',
            save_path=save_path,
            min_size=min_size,
            max_size=max_size,
            cache_name="pv_curtailment_map",
        )

    def _plot_station_map(
        self,
        values_by_station,
        unit_label,
        title,
        color,
        edgecolor,
        cache_name,
        save_path=None,
        min_size=20,
        max_size=2000,
    ):
        lons, lats, values, names = [], [], [], []

        for station_id, value in values_by_station.items():
            station = self.stations.get(station_id)
            if station is None:
                print(f"Warning: no coordinates for station '{station_id}', skipping.")
                continue
            lons.append(station['lon'])
            lats.append(station['lat'])
            values.append(value)
            names.append(station['name'])

        if not lons:
            print("No charging station data available to plot.")
            return

        gdf = gpd.GeoDataFrame(
            {'value': values, 'name': names},
            geometry=gpd.points_from_xy(lons, lats),
            crs="EPSG:4326",
        ).to_crs(epsg=3857)

        max_value = max(values)

        def size_for(value):
            if max_value == 0:
                return min_size
            return min_size + (max_size - min_size) * (value / max_value) ** 0.5

        sizes = [size_for(v) for v in values]

        fig, ax = plt.subplots(figsize=(10, 12))

        sc = ax.scatter(
            gdf.geometry.x,
            gdf.geometry.y,
            s=sizes,
            c=color,
            alpha=0.8,
            edgecolor=edgecolor,
            linewidth=0.5,
            zorder=2,
        )

        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords='offset points',
            fontsize=8,
            zorder=3,
            bbox={'boxstyle': 'round', 'fc': 'white', 'ec': edgecolor},
        )
        annot.set_visible(False)

        def update_annot(index):
            pos = sc.get_offsets()[index]
            annot.xy = pos
            annot.set_text(f"{names[index]}\n{values[index]:.2f} {unit_label}")

        def hover(event):
            visible = annot.get_visible()
            if event.inaxes != ax:
                if visible:
                    annot.set_visible(False)
                    fig.canvas.draw_idle()
                return

            contains, details = sc.contains(event)
            if contains:
                update_annot(details['ind'][0])
                annot.set_visible(True)
                fig.canvas.draw_idle()
            elif visible:
                annot.set_visible(False)
                fig.canvas.draw_idle()

        fig.canvas.mpl_connect('motion_notify_event', hover)

        _add_cached_basemap(ax, cache_name=cache_name)

        ax.set_axis_off()
        ax.set_title(title)

        plt.tight_layout()

        if save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)

        plt.show()


if __name__ == "__main__":
    stations_path = r"best-ebus\scenario\sumo\electric\e_stations.add.xml"
    chargingstations_path = (
        r"best-ebus\scenario\sumo\output"
        r"\electric_bus_2026-08-19-13-43-20_chargingstations.xml"
    )
    ess_path = (
        r"best-ebus\scenario\sumo\output"
        r"\electric_bus_2026-08-19-13-43-20_ess.xml"
    )

    csm = ChargingStationMap(stations_path, chargingstations_path, ess_path)
    csm.plot_energy_map(
        save_path=r"best-ebus\scenario\sumo\output\plots\charging_station_map.png"
    )
    csm.plot_pv_generation_map(
        save_path=r"best-ebus\scenario\sumo\output\plots\pv_generation_map.png"
    )
