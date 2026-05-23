#!/usr/bin/env python3
"""Build compact data assets for the interactive commute-time website."""

from __future__ import annotations

import csv
import heapq
import json
import math
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SITE_DATA_PATH = ROOT / "site" / "data" / "commute_map_data.json"

BOROUGHS_PATH = DATA_DIR / "uk_lad_boundaries.geojson"
TFL_OSI_PATH = DATA_DIR / "tfl_osi.ods"
TRAM_INTERCHANGES_PATH = DATA_DIR / "tram_interchanges.json"
NEIGHBOURHOOD_LABELS_PATH = DATA_DIR / "neighbourhood_labels.json"
# Optional London OSM basemap extracts. TODO: add a London Overpass refresh
# pipeline; until then, do not load stale upstream NYC extracts.
PARKS_PATH = DATA_DIR / "london_parks.geojson"
STREETS_PATH = DATA_DIR / "london_major_streets.json"
GTFS_PATH = DATA_DIR / "tfl_gtfs.zip"

GRID_COLS = 160
GRID_ROWS = 160
MIN_PARK_AREA = 70_000.0
# Keep walking assumptions close to a normal NYC walking pace so first/last-mile
# time does not dominate otherwise reasonable subway trips.
WALK_METERS_PER_MINUTE = 80.0
ACCESS_WALK_METERS_PER_MINUTE = 75.0
STATION_ACCESS_PENALTY = 3.5
CELL_NEAREST_STATIONS = 4
ORIGIN_NEAREST_STATIONS = 5
MAX_SHAPES_PER_ROUTE_DIRECTION = 2
INTER_COMPLEX_WALK_RADIUS = 260.0
INTER_COMPLEX_WALK_PENALTY = 2.0
DEFAULT_BOARD_WAIT = 4.0
TRANSFER_PENALTY = 4.0
IN_SCOPE_AGENCIES = {"LUL", "DLR", "TCL", "CV", "WFF", "CAB"}
AGENCY_WAIT_OVERRIDES = {
    "CV": 18.0,
    "WFF": 12.0,
    "CAB": 8.0,
}
REACHABILITY_AGENCIES = {"LUL", "DLR"}
REACHABILITY_ZONE = 1
REACHABILITY_THRESHOLD_MINUTES = 30.0

Point = Tuple[float, float]
Ring = List[Point]
Polygon = List[Ring]
MultiPolygon = List[Polygon]


def round_point(point: Point) -> List[float]:
    return [round(point[0], 1), round(point[1], 1)]


def round_path(points: Sequence[Point]) -> List[List[float]]:
    return [round_point(point) for point in points]


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def lonlat_to_xy(lon: float, lat: float, lat0: float) -> Point:
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = meters_per_deg_lat * math.cos(math.radians(lat0))
    return lon * meters_per_deg_lon, lat * meters_per_deg_lat


def osgb36_to_wgs84(easting: float, northing: float) -> Tuple[float, float]:
    airy_a = 6_377_563.396
    airy_b = 6_356_256.909
    national_grid_f0 = 0.9996012717
    lat0 = math.radians(49.0)
    lon0 = math.radians(-2.0)
    northing0 = -100_000.0
    easting0 = 400_000.0
    e2 = 1.0 - (airy_b * airy_b) / (airy_a * airy_a)
    n = (airy_a - airy_b) / (airy_a + airy_b)

    lat = lat0
    meridional_arc = 0.0
    while northing - northing0 - meridional_arc >= 0.00001:
        lat = (northing - northing0 - meridional_arc) / (airy_a * national_grid_f0) + lat
        meridional_arc = airy_b * national_grid_f0 * (
            (1 + n + 5 / 4 * n**2 + 5 / 4 * n**3) * (lat - lat0)
            - (3 * n + 3 * n**2 + 21 / 8 * n**3) * math.sin(lat - lat0) * math.cos(lat + lat0)
            + (15 / 8 * n**2 + 15 / 8 * n**3) * math.sin(2 * (lat - lat0)) * math.cos(2 * (lat + lat0))
            - 35 / 24 * n**3 * math.sin(3 * (lat - lat0)) * math.cos(3 * (lat + lat0))
        )

    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    nu = airy_a * national_grid_f0 / math.sqrt(1 - e2 * sin_lat**2)
    rho = airy_a * national_grid_f0 * (1 - e2) / (1 - e2 * sin_lat**2) ** 1.5
    eta2 = nu / rho - 1
    tan_lat = math.tan(lat)
    tan2 = tan_lat * tan_lat
    tan4 = tan2 * tan2
    sec_lat = 1 / cos_lat
    d_easting = easting - easting0

    vii = tan_lat / (2 * rho * nu)
    viii = tan_lat / (24 * rho * nu**3) * (5 + 3 * tan2 + eta2 - 9 * tan2 * eta2)
    ix = tan_lat / (720 * rho * nu**5) * (61 + 90 * tan2 + 45 * tan4)
    x = sec_lat / nu
    xi = sec_lat / (6 * nu**3) * (nu / rho + 2 * tan2)
    xii = sec_lat / (120 * nu**5) * (5 + 28 * tan2 + 24 * tan4)
    xiia = sec_lat / (5040 * nu**7) * (61 + 662 * tan2 + 1320 * tan4 + 720 * tan4 * tan2)

    osgb_lat = lat - vii * d_easting**2 + viii * d_easting**4 - ix * d_easting**6
    osgb_lon = lon0 + x * d_easting - xi * d_easting**3 + xii * d_easting**5 - xiia * d_easting**7

    x1, y1, z1 = ellipsoid_to_cartesian(osgb_lat, osgb_lon, 0.0, airy_a, airy_b)
    x2, y2, z2 = helmert_osgb36_to_wgs84(x1, y1, z1)
    wgs_lat, wgs_lon = cartesian_to_ellipsoid(x2, y2, z2, 6_378_137.0, 6_356_752.3141)
    return math.degrees(wgs_lon), math.degrees(wgs_lat)


def ellipsoid_to_cartesian(lat: float, lon: float, height: float, a: float, b: float) -> Tuple[float, float, float]:
    e2 = 1.0 - (b * b) / (a * a)
    nu = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    x = (nu + height) * math.cos(lat) * math.cos(lon)
    y = (nu + height) * math.cos(lat) * math.sin(lon)
    z = ((1 - e2) * nu + height) * math.sin(lat)
    return x, y, z


def helmert_osgb36_to_wgs84(x: float, y: float, z: float) -> Tuple[float, float, float]:
    tx, ty, tz = 446.448, -125.157, 542.060
    rx = math.radians(0.1502 / 3600)
    ry = math.radians(0.2470 / 3600)
    rz = math.radians(0.8421 / 3600)
    scale = -20.4894 * 1e-6
    return (
        tx + (1 + scale) * x - rz * y + ry * z,
        ty + rz * x + (1 + scale) * y - rx * z,
        tz - ry * x + rx * y + (1 + scale) * z,
    )


def cartesian_to_ellipsoid(x: float, y: float, z: float, a: float, b: float) -> Tuple[float, float]:
    e2 = 1.0 - (b * b) / (a * a)
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    while True:
        nu = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        next_lat = math.atan2(z + e2 * nu * math.sin(lat), p)
        if abs(next_lat - lat) < 1e-12:
            return next_lat, lon
        lat = next_lat


def boundary_point_to_xy(x: float, y: float, lat0: float) -> Point:
    lon, lat = osgb36_to_wgs84(x, y)
    return lonlat_to_xy(lon, lat, lat0)


def geometry_polygons(geometry: dict) -> list:
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    return []


def average_borough_latitude(payload: dict) -> float:
    latitudes = [
        float(feature["properties"]["LAT"])
        for feature in payload["features"]
        if str(feature.get("properties", {}).get("LAD24CD", "")).startswith("E09")
    ]
    return sum(latitudes) / max(len(latitudes), 1)


def ring_area(ring: Sequence[Point]) -> float:
    area = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def polygon_centroid(ring: Sequence[Point]) -> Point:
    area = ring_area(ring) or 1.0
    factor = 1.0 / (6.0 * area)
    cx = 0.0
    cy = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        cross = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    return cx * factor, cy * factor


def simplify_polyline(points: Sequence[Point], min_distance: float) -> List[Point]:
    if len(points) <= 2:
        return list(points)
    simplified = [points[0]]
    for point in points[1:-1]:
        if math.hypot(point[0] - simplified[-1][0], point[1] - simplified[-1][1]) >= min_distance:
            simplified.append(point)
    if points[-1] != simplified[-1]:
        simplified.append(points[-1])
    return simplified


def simplify_ring(ring: Sequence[Point], min_distance: float) -> Ring:
    if len(ring) <= 4:
        return list(ring)
    core = list(ring[:-1]) if ring[0] == ring[-1] else list(ring)
    simplified = [core[0]]
    for point in core[1:]:
        if math.hypot(point[0] - simplified[-1][0], point[1] - simplified[-1][1]) >= min_distance:
            simplified.append(point)
    if len(simplified) < 3:
        simplified = core[:3]
    simplified.append(simplified[0])
    return simplified


def bounds_of_ring(ring: Sequence[Point]) -> Tuple[float, float, float, float]:
    xs = [x for x, _ in ring]
    ys = [y for _, y in ring]
    return min(xs), min(ys), max(xs), max(ys)


def bounds_of_multipolygon(multipolygon: MultiPolygon) -> Tuple[float, float, float, float]:
    xs = [x for polygon in multipolygon for ring in polygon for x, _ in ring]
    ys = [y for polygon in multipolygon for ring in polygon for _, y in ring]
    return min(xs), min(ys), max(xs), max(ys)


def bounds_of_points(points: Sequence[Point]) -> Tuple[float, float, float, float]:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_intersects(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def point_in_ring(point: Point, ring: Sequence[Point]) -> bool:
    x, y = point
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        intersects = (yi > y) != (yj > y)
        if intersects:
            x_hit = (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
            if x < x_hit:
                inside = not inside
        j = i
    return inside


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    if not polygon:
        return False
    if not point_in_ring(point, polygon[0]):
        return False
    for hole in polygon[1:]:
        if point_in_ring(point, hole):
            return False
    return True


def point_in_multipolygon(point: Point, multipolygon: MultiPolygon) -> bool:
    return any(point_in_polygon(point, polygon) for polygon in multipolygon)


def edge_key(start: Sequence[float], end: Sequence[float]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    a = (round(start[0], 7), round(start[1], 7))
    b = (round(end[0], 7), round(end[1], 7))
    return (a, b) if a <= b else (b, a)


def union_outline_from_features(features: Sequence[dict], lat0: float) -> MultiPolygon:
    directed_edges: Dict[Tuple[Tuple[float, float], Tuple[float, float]], Tuple[Tuple[float, float], Tuple[float, float]]] = {}
    edge_counts: Counter[Tuple[Tuple[float, float], Tuple[float, float]]] = Counter()

    for feature in features:
        geometry = feature["geometry"]
        for polygon_coords in geometry_polygons(geometry):
            if not polygon_coords:
                continue
            ring_coords = polygon_coords[0]
            for start, end in zip(ring_coords, ring_coords[1:]):
                key = edge_key(start, end)
                edge_counts[key] += 1
                directed_edges.setdefault(
                    key,
                    ((round(start[0], 7), round(start[1], 7)), (round(end[0], 7), round(end[1], 7))),
                )

    adjacency: Dict[Tuple[float, float], List[Tuple[float, float]]] = defaultdict(list)
    for key, count in edge_counts.items():
        if count != 1:
            continue
        start, end = directed_edges[key]
        adjacency[start].append(end)

    rings_lonlat: List[List[Tuple[float, float]]] = []
    while adjacency:
        start = next(iter(adjacency))
        ring = [start]
        current = start
        while True:
            next_points = adjacency.get(current)
            if not next_points:
                break
            next_point = next_points.pop()
            if not next_points:
                del adjacency[current]
            ring.append(next_point)
            current = next_point
            if current == start:
                break
        if len(ring) >= 4 and ring[0] == ring[-1]:
            rings_lonlat.append(ring)

    polygons = []
    for ring_coords in rings_lonlat:
        ring = [boundary_point_to_xy(x, y, lat0) for x, y in ring_coords]
        polygons.append([simplify_ring(ring, 120.0)])
    return polygons


def extract_boroughs(payload: dict, lat0: float) -> Tuple[list, MultiPolygon]:
    boroughs = []
    london_features = [
        feature
        for feature in payload["features"]
        if str(feature.get("properties", {}).get("LAD24CD", "")).startswith("E09")
    ]
    if len(london_features) != 33:
        raise ValueError(f"Expected 33 London LAD features, found {len(london_features)}")

    for feature in london_features:
        geometry = feature["geometry"]
        multipolygon: MultiPolygon = []
        for polygon_coords in geometry_polygons(geometry):
            polygon: Polygon = []
            for ring_coords in polygon_coords:
                ring = [boundary_point_to_xy(x, y, lat0) for x, y in ring_coords]
                polygon.append(simplify_ring(ring, 120.0))
            multipolygon.append(polygon)
        boroughs.append(
            {
                "name": feature["properties"]["LAD24NM"],
                "polygons": [[round_path(ring) for ring in polygon] for polygon in multipolygon],
            }
        )
    return boroughs, union_outline_from_features(london_features, lat0)


def load_neighbourhood_labels(lat0: float) -> list:
    payload = load_json(NEIGHBOURHOOD_LABELS_PATH)
    labels = []
    for item in payload.get("labels", []):
        labels.append(
            {
                "name": item["name"],
                "point": round_point(lonlat_to_xy(float(item["lon"]), float(item["lat"]), lat0)),
            }
        )
    return labels


def extract_parks(lat0: float, bbox: Tuple[float, float, float, float]) -> list:
    if not PARKS_PATH.exists():
        return []
    payload = load_json(PARKS_PATH)
    parks = []
    for feature in payload["features"]:
        try:
            area = float(feature["properties"].get("shape_area") or 0.0)
        except (TypeError, ValueError):
            area = 0.0
        if area < MIN_PARK_AREA:
            continue
        geometry = feature.get("geometry")
        if not geometry:
            continue
        polygons = []
        if geometry["type"] == "Polygon":
            polygons = [geometry["coordinates"]]
        elif geometry["type"] == "MultiPolygon":
            polygons = geometry["coordinates"]
        for polygon_coords in polygons:
            polygon: Polygon = []
            for ring_coords in polygon_coords:
                ring = [lonlat_to_xy(lon, lat, lat0) for lon, lat in ring_coords]
                polygon.append(simplify_ring(ring, 90.0))
            if polygon and bbox_intersects(bounds_of_ring(polygon[0]), bbox):
                parks.append([round_path(ring) for ring in polygon])
    return parks


def extract_streets(lat0: float, bbox: Tuple[float, float, float, float]) -> list:
    if not STREETS_PATH.exists():
        return []
    payload = load_json(STREETS_PATH)
    allowed = {"motorway", "trunk", "primary"}
    streets = []
    for element in payload.get("elements", []):
        if element.get("type") != "way":
            continue
        tags = element.get("tags", {})
        kind = tags.get("highway")
        if kind not in allowed or "geometry" not in element or "name" not in tags:
            continue
        points = [lonlat_to_xy(node["lon"], node["lat"], lat0) for node in element["geometry"]]
        if len(points) < 2:
            continue
        length = sum(distance for distance in (
            math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
            for i in range(len(points) - 1)
        ))
        if kind == "primary" and length < 900.0:
            continue
        simplified = simplify_polyline(points, 220.0)
        if len(simplified) < 2 or not bbox_intersects(bounds_of_points(simplified), bbox):
            continue
        streets.append({"kind": kind, "name": tags["name"], "points": round_path(simplified)})
    return streets


def build_external_land_polygons(
    lat0: float,
    bbox: Tuple[float, float, float, float],
    borough_polygons: MultiPolygon,
) -> list:
    return []


def read_csv_from_zip(gtfs_path: Path, member: str) -> Iterable[dict]:
    with zipfile.ZipFile(gtfs_path) as archive:
        with archive.open(member) as handle:
            reader = csv.DictReader(line.decode("utf-8-sig") for line in handle)
            yield from reader


def ods_cell_text(cell: ET.Element, namespace: dict) -> str:
    return " ".join("".join(paragraph.itertext()) for paragraph in cell.findall("text:p", namespace)).strip()


def ods_rows(path: Path) -> Iterable[list[str]]:
    namespace = {
        "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
        "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    }
    table_cell = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-cell"
    columns_repeated = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}number-columns-repeated"
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    for row in root.findall(".//table:table-row", namespace):
        values: list[str] = []
        for cell in row.findall(table_cell):
            repeat = int(cell.attrib.get(columns_repeated, "1"))
            values.extend([ods_cell_text(cell, namespace)] * min(repeat, 32))
        if any(values):
            yield values


def parse_minutes_tenths(value: str) -> float | None:
    try:
        return float(value) / 10.0
    except (TypeError, ValueError):
        return None


def load_osi_edges() -> list[tuple[str, str, float]]:
    rows = list(ods_rows(TFL_OSI_PATH))
    header_index = next(index for index, row in enumerate(rows) if "Station_A_Name" in row)
    header = rows[header_index]
    column_index = {name: header.index(name) for name in ("Station_A_Name", "Station_B_Name", "InterchangeTimeAB", "InterchangeTimeBA")}
    edges: list[tuple[str, str, float]] = []
    for row in rows[header_index + 1:]:
        if len(row) <= max(column_index.values()):
            continue
        station_a = row[column_index["Station_A_Name"]]
        station_b = row[column_index["Station_B_Name"]]
        minutes_ab = parse_minutes_tenths(row[column_index["InterchangeTimeAB"]])
        minutes_ba = parse_minutes_tenths(row[column_index["InterchangeTimeBA"]])
        if station_a and station_b and minutes_ab is not None:
            edges.append((station_a, station_b, minutes_ab))
        if station_a and station_b and minutes_ba is not None:
            edges.append((station_b, station_a, minutes_ba))
    return edges


def load_tram_interchange_edges() -> list[tuple[str, str, float]]:
    payload = load_json(TRAM_INTERCHANGES_PATH)
    return [
        (edge["from"], edge["to"], float(edge["minutes"]))
        for edge in payload.get("edges", [])
    ]


def parse_zones(value: str) -> list[int]:
    zones = []
    for item in re.split(r"[/,;+ ]+", value.strip()):
        if not item:
            continue
        try:
            zones.append(int(item))
        except ValueError:
            continue
    return sorted(set(zones))


def load_station_zone_index() -> Dict[str, list[int]]:
    with open(DATA_DIR / "tfl_stations.csv", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        name_column = next((name for name in fieldnames if name.lower() in {"name", "station", "station_name"}), None)
        zone_column = next((name for name in fieldnames if name.lower() in {"zone", "zones", "fare_zone"}), None)
        if not name_column or not zone_column:
            raise ValueError(f"Could not identify station name/zone columns in tfl_stations.csv: {fieldnames}")
        zone_index: Dict[str, list[int]] = {}
        for row in reader:
            station_name = row.get(name_column, "")
            zones = parse_zones(row.get(zone_column, ""))
            if station_name and zones:
                zone_index[canonical_station_name(station_name)] = zones
        return zone_index


def parse_gtfs_time(value: str) -> int:
    hours, minutes, seconds = map(int, value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def load_in_scope_agencies() -> set[str]:
    agency_ids = {row["agency_id"] for row in read_csv_from_zip(GTFS_PATH, "agency.txt")}
    return agency_ids & IN_SCOPE_AGENCIES


def build_station_data(lat0: float) -> Tuple[list, Dict[str, int], Dict[str, str]]:
    complex_info: Dict[str, dict] = {}
    stop_to_complex: Dict[str, str] = {}

    for row in read_csv_from_zip(GTFS_PATH, "stops.txt"):
        stop_id = row["stop_id"]
        station_id = row["stop_name"]
        stop_to_complex[stop_id] = station_id
        info = complex_info.setdefault(
            station_id,
            {
                "id": station_id,
                "name": station_id,
                "points": [],
                "routes": set(),
            },
        )
        info["points"].append(lonlat_to_xy(float(row["stop_lon"]), float(row["stop_lat"]), lat0))

    stations = []
    station_index_by_id: Dict[str, int] = {}
    for complex_id, info in sorted(complex_info.items()):
        points = info.pop("points")
        info["point"] = (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )
        station_index_by_id[complex_id] = len(stations)
        stations.append(info)

    return stations, station_index_by_id, stop_to_complex


def build_route_segments(points: Sequence[Point], gla_polygons: MultiPolygon) -> list:
    return [
        {
            "points": round_path([start, end]),
            "insideGla": point_in_multipolygon(
                ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0),
                gla_polygons,
            ),
        }
        for start, end in zip(points, points[1:])
    ]


def build_routes_and_shapes(lat0: float, bbox: Tuple[float, float, float, float], gla_polygons: MultiPolygon) -> Tuple[dict, list, dict]:
    in_scope_agencies = load_in_scope_agencies()
    route_styles = {}
    for row in read_csv_from_zip(GTFS_PATH, "routes.txt"):
        agency_id = row.get("agency_id", "")
        if agency_id not in in_scope_agencies:
            continue
        route_styles[row["route_id"]] = {
            "color": f"#{row['route_color'] or '808183'}",
            "textColor": f"#{row['route_text_color'] or 'FFFFFF'}",
            "label": row["route_short_name"] or row["route_id"],
            "agencyId": agency_id,
        }

    trips_by_id = {}
    shape_counts: Dict[Tuple[str, str], Counter[str]] = {}
    for row in read_csv_from_zip(GTFS_PATH, "trips.txt"):
        route_id = row["route_id"]
        if route_id not in route_styles:
            continue
        trips_by_id[row["trip_id"]] = {
            "route_id": route_id,
            "agency_id": route_styles[route_id]["agencyId"],
            "direction_id": row.get("direction_id", "0"),
            "service_id": row.get("service_id", ""),
        }
        shape_counts.setdefault((route_id, row.get("direction_id", "0")), Counter())[row["shape_id"]] += 1

    selected_shape_ids = {}
    for (route_id, _direction), counter in shape_counts.items():
        for shape_id, _count in counter.most_common(MAX_SHAPES_PER_ROUTE_DIRECTION):
            selected_shape_ids[shape_id] = route_id

    points_by_shape = defaultdict(list)
    for row in read_csv_from_zip(GTFS_PATH, "shapes.txt"):
        shape_id = row["shape_id"]
        if shape_id not in selected_shape_ids:
            continue
        point = lonlat_to_xy(float(row["shape_pt_lon"]), float(row["shape_pt_lat"]), lat0)
        points_by_shape[shape_id].append((int(row["shape_pt_sequence"]), point))

    shapes = []
    for shape_id, route_id in selected_shape_ids.items():
        points = [point for _, point in sorted(points_by_shape.get(shape_id, []))]
        points = simplify_polyline(points, 90.0)
        if len(points) < 2 or not bbox_intersects(bounds_of_points(points), bbox):
            continue
        shapes.append(
            {
                "routeId": route_id,
                "color": route_styles[route_id]["color"],
                "textColor": route_styles[route_id]["textColor"],
                "label": route_styles[route_id]["label"],
                "points": round_path(points),
                "segments": build_route_segments(points, gla_polygons),
            }
        )
    return route_styles, shapes, trips_by_id


def build_route_waits(trips_by_id: dict, route_styles: dict) -> Dict[str, float]:
    departures_by_route_service: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    current_trip_id = None
    first_departure = None

    for row in read_csv_from_zip(GTFS_PATH, "stop_times.txt"):
        trip_id = row["trip_id"]
        stop_sequence = int(row["stop_sequence"])
        if trip_id != current_trip_id:
            if current_trip_id and first_departure is not None and current_trip_id in trips_by_id:
                trip = trips_by_id[current_trip_id]
                departures_by_route_service[(trip["route_id"], trip["service_id"])].append(first_departure)
            current_trip_id = trip_id
            first_departure = parse_gtfs_time(row["departure_time"]) if stop_sequence == 1 else None
        elif stop_sequence == 1 and first_departure is None:
            first_departure = parse_gtfs_time(row["departure_time"])

    if current_trip_id and first_departure is not None and current_trip_id in trips_by_id:
        trip = trips_by_id[current_trip_id]
        departures_by_route_service[(trip["route_id"], trip["service_id"])].append(first_departure)

    waits_by_route: Dict[str, List[float]] = defaultdict(list)
    for (route_id, _service_id), departures in departures_by_route_service.items():
        departures = sorted(set(departures))
        gaps = [
            (departures[i + 1] - departures[i]) / 60.0
            for i in range(len(departures) - 1)
            if 2 * 60 <= departures[i + 1] - departures[i] <= 30 * 60
        ]
        if gaps:
            waits_by_route[route_id].append(statistics.median(gaps) / 2.0)

    route_waits: Dict[str, float] = {}
    for route_id, waits in waits_by_route.items():
        route_waits[route_id] = round(clamp(statistics.median(waits), 1.5, 8.0), 2)
    for route_id, style in route_styles.items():
        agency_id = style.get("agencyId", "")
        if agency_id in AGENCY_WAIT_OVERRIDES:
            route_waits[route_id] = AGENCY_WAIT_OVERRIDES[agency_id]
    return route_waits


def route_wait_minutes(route_id: str, route_styles: dict, route_waits: Dict[str, float]) -> float:
    agency_id = route_styles.get(route_id, {}).get("agencyId", "")
    return route_waits.get(route_id, AGENCY_WAIT_OVERRIDES.get(agency_id, DEFAULT_BOARD_WAIT))


OSI_NAME_ALIASES = {
    "balham": "balham",
    "blackfriars": "blackfriars",
    "charing x": "charing cross",
    "edgware rd b": "edgware road bakerloo",
    "edgware rd c&h": "edgware road circle line",
    "elephant & c": "elephant & castle",
    "euston": "euston",
    "finchley rd": "finchley road",
    "finsbury pk": "finsbury park",
    "hammersmith c&h": "hammersmith h&c",
    "hammersmith d&p": "hammersmith dist&picc",
    "kings cross": "kings cross st pancras",
    "oxford circ": "oxford circus",
    "tottenham ct rd": "tottenham court road",
    "tower gatewy dlr": "tower gateway",
    "tower gatewy": "tower gateway",
    "custom house": "custom house for excel",
    "shepherds bsh": "shepherds bush central",
    "tottenham h": "tottenham hale",
    "sudbury hil": "sudbury hill",
    "w india quay": "west india quay",
    "w hampstead": "west hampstead",
    "victoria d": "victoria",
    "victoria v": "victoria",
    "walthmstow c": "walthamstow central",
    "woolwch arsn": "woolwich arsenal",
}

OUT_OF_SCOPE_OSI_NAMES = {
    "Battersea Park",
    "Battersea Pwr S",
    "Bowes Park",
    "Bromley North",
    "Bromley South",
    "Brondesbury",
    "Camden Road",
    "Catford",
    "Catford Bridge",
    "Clapham High St",
    "Clock House",
    "Dalston Junction",
    "Dalston Kingsld",
    "Finchley Rd Fgnl",
    "Forest Gate",
    "Hackney Central",
    "Hackney Downs",
    "Harringay",
    "Harringay Grn Ln",
    "Highbury",
    "Kent House",
    "Kentish Tn West",
    "Leytonstone H Rd",
    "Manor Park",
    "New Cross",
    "New Cross Gate",
    "Penge East",
    "Penge West",
    "Putney",
    "Queenstown Road",
    "Same NLC OSI",
    "South Tottenham",
    "Southend Central",
    "Southend Victoria",
    "St Pancras Intl",
    "Stevenage",
    "Sudbury Hill Hrw",
    "Upper Holloway",
    "Upper Warlingham",
    "Walthamstow Q Rd",
    "Walthamstw Qns Rd",
    "Wanstead Park",
    "Waterloo E NR",
    "Welwyn Garden City",
    "Whyteleafe",
    "Woodgrange Park",
    "Woolwich",
}


def is_out_of_scope_osi_name(name: str) -> bool:
    return (
        name in OUT_OF_SCOPE_OSI_NAMES
        or name.endswith(" NR")
        or name.endswith(" LO")
        or name.endswith(" EL")
        or name.endswith(" Tlnk")
    )


def canonical_station_name(name: str) -> str:
    canonical = name.lower().replace(".", "").replace("'", "").replace(" and ", " & ")
    canonical = canonical.replace("(dist&picc line)", "dist&picc")
    canonical = canonical.replace("(h&c line)", "h&c")
    canonical = canonical.replace("(", " ").replace(")", " ")
    for suffix in (
        " underground station",
        " dlr station",
        " tram stop",
        " station",
        " pier",
        " lu",
        " dlr",
    ):
        if canonical.endswith(suffix):
            canonical = canonical[: -len(suffix)]
    canonical = " ".join(canonical.split())
    canonical = OSI_NAME_ALIASES.get(canonical, canonical)
    canonical = re.sub(r"\bst\b", "street", canonical)
    return OSI_NAME_ALIASES.get(canonical, canonical)


def station_name_index(stations: list) -> Dict[str, List[int]]:
    index: Dict[str, List[int]] = defaultdict(list)
    for station_index, station in enumerate(stations):
        index[canonical_station_name(station["name"])].append(station_index)
    return index


def resolve_interchange_edges(
    edges: Sequence[tuple[str, str, float]],
    stations: list,
    label: str,
) -> tuple[list[tuple[int, int, float]], set[tuple[int, int]], set[str]]:
    name_index = station_name_index(stations)
    resolved: list[tuple[int, int, float]] = []
    official_pairs: set[tuple[int, int]] = set()
    unmatched: set[str] = set()
    ignored: set[str] = set()
    for from_name, to_name, minutes in edges:
        from_indexes = name_index.get(canonical_station_name(from_name), [])
        to_indexes = name_index.get(canonical_station_name(to_name), [])
        if not from_indexes:
            (ignored if is_out_of_scope_osi_name(from_name) else unmatched).add(from_name)
        if not to_indexes:
            (ignored if is_out_of_scope_osi_name(to_name) else unmatched).add(to_name)
        if not from_indexes or not to_indexes:
            continue
        for from_station in from_indexes:
            for to_station in to_indexes:
                if from_station == to_station:
                    continue
                resolved.append((from_station, to_station, minutes))
                official_pairs.add((from_station, to_station))
    print(f"{label} unmatched station names ({len(unmatched)}): {', '.join(sorted(unmatched)) or 'none'}")
    if ignored:
        print(f"{label} ignored out-of-scope station names ({len(ignored)}): {', '.join(sorted(ignored))}")
    return resolved, official_pairs, unmatched


def build_graph(
    stations: list,
    station_index_by_id: Dict[str, int],
    stop_to_complex: Dict[str, str],
    trips_by_id: dict,
    route_styles: dict,
    route_waits: Dict[str, float],
    official_interchanges: Sequence[tuple[int, int, float]],
    official_station_pairs: set[tuple[int, int]],
) -> Tuple[list, list, list]:
    durations_by_edge: Dict[Tuple[int, int, str], List[float]] = defaultdict(list)
    current_trip_id = None
    current_rows: List[dict] = []

    def process_trip(trip_id: str, rows: List[dict]) -> None:
        trip = trips_by_id.get(trip_id)
        if not trip or len(rows) < 2:
            return
        route_id = trip["route_id"]
        ordered = sorted(rows, key=lambda row: int(row["stop_sequence"]))
        for row in ordered:
            stop_id = row["stop_id"]
            complex_id = stop_to_complex.get(stop_id)
            if complex_id in station_index_by_id:
                stations[station_index_by_id[complex_id]]["routes"].add(route_id)
        for prev, nxt in zip(ordered, ordered[1:]):
            from_complex = stop_to_complex.get(prev["stop_id"])
            to_complex = stop_to_complex.get(nxt["stop_id"])
            if not from_complex or not to_complex or from_complex == to_complex:
                continue
            if from_complex not in station_index_by_id or to_complex not in station_index_by_id:
                continue
            duration_seconds = parse_gtfs_time(nxt["arrival_time"]) - parse_gtfs_time(prev["departure_time"])
            if 20 <= duration_seconds <= 1800:
                from_index = station_index_by_id[from_complex]
                to_index = station_index_by_id[to_complex]
                durations_by_edge[(from_index, to_index, route_id)].append(duration_seconds / 60.0)

    for row in read_csv_from_zip(GTFS_PATH, "stop_times.txt"):
        trip_id = row["trip_id"]
        if current_trip_id is None:
            current_trip_id = trip_id
        if trip_id != current_trip_id:
            process_trip(current_trip_id, current_rows)
            current_trip_id = trip_id
            current_rows = []
        current_rows.append(row)
    if current_trip_id and current_rows:
        process_trip(current_trip_id, current_rows)

    route_states = []
    state_index_by_key: Dict[Tuple[int, str], int] = {}
    station_states: List[List[int]] = [[] for _ in stations]
    for station_index, station in enumerate(stations):
        for route_id in sorted(station["routes"]):
            state_index_by_key[(station_index, route_id)] = len(route_states)
            route_states.append({"stationIndex": station_index, "routeId": route_id})
            station_states[station_index].append(state_index_by_key[(station_index, route_id)])

    adjacency = [dict() for _ in route_states]
    fixed_adjacency = [dict() for _ in route_states]
    for (from_station, to_station, route_id), durations in durations_by_edge.items():
        from_state = state_index_by_key.get((from_station, route_id))
        to_state = state_index_by_key.get((to_station, route_id))
        if from_state is None or to_state is None:
            continue
        weight = round(statistics.median(durations), 2)
        existing = adjacency[from_state].get(to_state)
        if existing is None or weight < existing:
            adjacency[from_state][to_state] = weight

    for station_index, state_indexes in enumerate(station_states):
        for from_state in state_indexes:
            for to_state in state_indexes:
                if from_state == to_state:
                    continue
                to_route = route_states[to_state]["routeId"]
                transfer_cost = round(TRANSFER_PENALTY + route_wait_minutes(to_route, route_styles, route_waits), 2)
                existing = adjacency[from_state].get(to_state)
                if existing is None or transfer_cost < existing:
                    adjacency[from_state][to_state] = transfer_cost

    for from_station, to_station, minutes in official_interchanges:
        for from_state in station_states[from_station]:
            for to_state in station_states[to_station]:
                existing = fixed_adjacency[from_state].get(to_state)
                if existing is None or minutes < existing:
                    fixed_adjacency[from_state][to_state] = round(minutes, 2)

    for i, source in enumerate(stations):
        sx, sy = source["point"]
        for j in range(i + 1, len(stations)):
            if (i, j) in official_station_pairs or (j, i) in official_station_pairs:
                continue
            tx, ty = stations[j]["point"]
            distance = math.hypot(tx - sx, ty - sy)
            if distance > INTER_COMPLEX_WALK_RADIUS:
                continue
            walk_minutes = distance / WALK_METERS_PER_MINUTE + INTER_COMPLEX_WALK_PENALTY
            for from_state in station_states[i]:
                for to_state in station_states[j]:
                    to_route = route_states[to_state]["routeId"]
                    from_route = route_states[from_state]["routeId"]
                    forward_cost = round(
                        walk_minutes + TRANSFER_PENALTY + route_wait_minutes(to_route, route_styles, route_waits),
                        2,
                    )
                    backward_cost = round(
                        walk_minutes + TRANSFER_PENALTY + route_wait_minutes(from_route, route_styles, route_waits),
                        2,
                    )
                    existing_forward = adjacency[from_state].get(to_state)
                    existing_backward = adjacency[to_state].get(from_state)
                    if existing_forward is None or forward_cost < existing_forward:
                        adjacency[from_state][to_state] = forward_cost
                    if existing_backward is None or backward_cost < existing_backward:
                        adjacency[to_state][from_state] = backward_cost

    return (
        route_states,
        station_states,
        build_adjacency_payload(adjacency, fixed_adjacency),
    )


def build_adjacency_payload(adjacency: list[dict], fixed_adjacency: list[dict]) -> list:
    payload = []
    for edges, fixed_edges in zip(adjacency, fixed_adjacency):
        row = []
        for to_index in sorted(set(edges) | set(fixed_edges)):
            if to_index in fixed_edges:
                row.append([to_index, fixed_edges[to_index], "fixedInterchange"])
            else:
                row.append([to_index, edges[to_index]])
        payload.append(row)
    return payload


def enrich_station_zones(stations: list, route_styles: dict) -> None:
    zone_index = load_station_zone_index()
    reconciliation = load_json(DATA_DIR / "tfl_station_zone_reconciliation.json")
    unmatched_lul_dlr = []
    tagged_count = 0
    for station in stations:
        csv_name = reconciliation.get(station["name"], station["name"])
        zones = zone_index.get(canonical_station_name(csv_name))
        if zones:
            station["zones"] = zones
            tagged_count += 1
            continue
        station_agencies = {route_styles.get(route_id, {}).get("agencyId") for route_id in station["routes"]}
        if station_agencies & {"LUL", "DLR"}:
            unmatched_lul_dlr.append(station["name"])
    print(f"Zone-tagged stations: {tagged_count}/{len(stations)}")
    print(f"Unmatched LUL/DLR zone stations ({len(unmatched_lul_dlr)}): {', '.join(sorted(unmatched_lul_dlr)) or 'none'}")


def station_agency_ids(station: dict, route_styles: dict) -> set[str]:
    return {
        route_styles.get(route_id, {}).get("agencyId", "")
        for route_id in station["routes"]
    }


def central_reachability_station_indexes(stations: list, route_styles: dict) -> list[int]:
    return [
        station_index
        for station_index, station in enumerate(stations)
        if station.get("insideGla", False)
        and REACHABILITY_ZONE in (station.get("zones") or [])
        and station_agency_ids(station, route_styles) & REACHABILITY_AGENCIES
    ]


def nearest_station_accesses(point: Point, stations: list, count: int, inside_gla_only: bool = True) -> list[tuple[int, float]]:
    ranked = sorted(
        (
            (
                station_index,
                math.hypot(station["point"][0] - point[0], station["point"][1] - point[1]) / ACCESS_WALK_METERS_PER_MINUTE
                + STATION_ACCESS_PENALTY,
            )
            for station_index, station in enumerate(stations)
            if not inside_gla_only or station.get("insideGla", False)
        ),
        key=lambda item: item[1],
    )
    return ranked[:count]


def dijkstra_from_accesses(
    accesses: Sequence[Sequence[float]],
    route_states: list,
    station_states: list,
    adjacency: list,
    route_styles: dict,
    route_waits: Dict[str, float],
) -> list[float]:
    distances = [math.inf] * len(route_states)
    heap: list[tuple[float, int]] = []
    for station_index, walk_minutes in accesses:
        for route_state_index in station_states[int(station_index)]:
            route_id = route_states[route_state_index]["routeId"]
            candidate = float(walk_minutes) + route_wait_minutes(route_id, route_styles, route_waits)
            if candidate < distances[route_state_index]:
                distances[route_state_index] = candidate
                heapq.heappush(heap, (candidate, route_state_index))

    while heap:
        current_distance, current_index = heapq.heappop(heap)
        if current_distance != distances[current_index]:
            continue
        for edge in adjacency[current_index]:
            next_index = int(edge[0])
            candidate = current_distance + float(edge[1])
            if candidate < distances[next_index]:
                distances[next_index] = candidate
                heapq.heappush(heap, (candidate, next_index))
    return distances


def add_zone1_reachability_scores(
    cells: list,
    stations: list,
    route_styles: dict,
    route_waits: Dict[str, float],
    route_states: list,
    station_states: list,
    adjacency: list,
) -> int:
    target_station_indexes = central_reachability_station_indexes(stations, route_styles)
    target_accesses = {
        station_index: nearest_station_accesses(stations[station_index]["point"], stations, CELL_NEAREST_STATIONS)
        for station_index in target_station_indexes
    }
    denominator = len(target_station_indexes)
    for cell in cells:
        distances = dijkstra_from_accesses(
            cell["access"],
            route_states,
            station_states,
            adjacency,
            route_styles,
            route_waits,
        )
        reachable = 0
        for station_index in target_station_indexes:
            station_point = stations[station_index]["point"]
            direct_walk_minutes = math.hypot(station_point[0] - cell["point"][0], station_point[1] - cell["point"][1]) / WALK_METERS_PER_MINUTE
            best_minutes = direct_walk_minutes
            for access_station_index, egress_minutes in target_accesses[station_index]:
                for route_state_index in station_states[access_station_index]:
                    best_minutes = min(best_minutes, distances[route_state_index] + egress_minutes)
            if best_minutes <= REACHABILITY_THRESHOLD_MINUTES:
                reachable += 1
        cell["zone1ReachableStations"] = reachable
        cell["zone1ReachabilityScore"] = round(reachable / denominator, 4) if denominator else 0.0
    print(
        "Zone 1 reachability denominator: "
        f"{denominator} LUL/DLR stations within {REACHABILITY_THRESHOLD_MINUTES:g} min threshold"
    )
    return denominator


def mark_stations_inside_gla(stations: list, gla_polygons: MultiPolygon) -> None:
    for station in stations:
        station["insideGla"] = point_in_multipolygon(station["point"], gla_polygons)


def build_grid_cells(polygons: MultiPolygon, stations: list, bbox: Tuple[float, float, float, float]) -> Tuple[list, list]:
    min_x, min_y, max_x, max_y = bbox
    cell_w = (max_x - min_x) / GRID_COLS
    cell_h = (max_y - min_y) / GRID_ROWS
    mask = []
    cells = []
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            x = min_x + (col + 0.5) * cell_w
            y = min_y + (row + 0.5) * cell_h
            point = (x, y)
            if not point_in_multipolygon(point, polygons):
                mask.append(-1)
                continue
            ranked = sorted(
                (
                    (
                        station_index,
                        round(
                            math.hypot(station_point[0] - x, station_point[1] - y) / ACCESS_WALK_METERS_PER_MINUTE
                            + STATION_ACCESS_PENALTY,
                            2,
                        ),
                    )
                    for station_index, station in enumerate(stations)
                    if station.get("insideGla", False)
                    for station_point in [station["point"]]
                ),
                key=lambda item: item[1],
            )[:CELL_NEAREST_STATIONS]
            cells.append(
                {
                    "col": col,
                    "row": row,
                    "point": round_point(point),
                    "access": [[station_index, walk_minutes] for station_index, walk_minutes in ranked],
                }
            )
            mask.append(len(cells) - 1)
    return cells, mask


def main() -> None:
    borough_payload = load_json(BOROUGHS_PATH)
    lat0 = average_borough_latitude(borough_payload)
    boroughs, all_polygons = extract_boroughs(borough_payload, lat0)
    labels = load_neighbourhood_labels(lat0)
    bbox = bounds_of_multipolygon(all_polygons)
    external_land = build_external_land_polygons(lat0, bbox, all_polygons)
    parks = extract_parks(lat0, bbox)
    streets = extract_streets(lat0, bbox)
    stations, station_index_by_id, stop_to_complex = build_station_data(lat0)
    mark_stations_inside_gla(stations, all_polygons)
    route_styles, route_shapes, trips_by_id = build_routes_and_shapes(lat0, bbox, all_polygons)
    route_waits = build_route_waits(trips_by_id, route_styles)
    loaded_agencies = load_in_scope_agencies()
    trip_agencies = {trip["agency_id"] for trip in trips_by_id.values()}
    print(
        "Loaded "
        f"{len(loaded_agencies)} agencies, {len(route_styles)} routes, "
        f"{len(trips_by_id)} trips across {len(trip_agencies)} agencies, "
        f"{len(stations)} stations"
    )
    missing_trip_agencies = sorted(loaded_agencies - trip_agencies)
    if missing_trip_agencies:
        print(f"Agencies without trips in this feed: {', '.join(missing_trip_agencies)}")
    osi_edges = load_osi_edges()
    tram_edges = load_tram_interchange_edges()
    print(f"OSI edges loaded: {len(osi_edges)}")
    resolved_osi_edges, osi_station_pairs, _osi_unmatched = resolve_interchange_edges(osi_edges, stations, "OSI")
    resolved_tram_edges, tram_station_pairs, _tram_unmatched = resolve_interchange_edges(tram_edges, stations, "Tram")
    official_interchanges = resolved_osi_edges + resolved_tram_edges
    official_station_pairs = osi_station_pairs | tram_station_pairs
    print(f"Official interchange edges matched: {len(official_interchanges)}")
    route_states, station_states, adjacency = build_graph(
        stations,
        station_index_by_id,
        stop_to_complex,
        trips_by_id,
        route_styles,
        route_waits,
        official_interchanges,
        official_station_pairs,
    )
    enrich_station_zones(stations, route_styles)
    cells, mask = build_grid_cells(all_polygons, stations, bbox)
    central_reachability_station_count = add_zone1_reachability_scores(
        cells,
        stations,
        route_styles,
        route_waits,
        route_states,
        station_states,
        adjacency,
    )

    output = {
        "meta": {
            "lat0": round(lat0, 6),
            "bounds": [round(value, 1) for value in bbox],
            "gridCols": GRID_COLS,
            "gridRows": GRID_ROWS,
            "walkMetersPerMinute": WALK_METERS_PER_MINUTE,
            "accessWalkMetersPerMinute": ACCESS_WALK_METERS_PER_MINUTE,
            "stationAccessPenalty": STATION_ACCESS_PENALTY,
            "originStationCount": ORIGIN_NEAREST_STATIONS,
            "cellNearestStations": CELL_NEAREST_STATIONS,
            "defaultBoardWait": DEFAULT_BOARD_WAIT,
            "transferPenalty": TRANSFER_PENALTY,
            "centralReachabilityStationCount": central_reachability_station_count,
            "centralReachabilityThresholdMinutes": int(REACHABILITY_THRESHOLD_MINUTES),
        },
        "boroughs": boroughs,
        "labels": labels,
        "geography": {
            "outline": [[round_path(ring) for ring in polygon] for polygon in all_polygons],
            "boroughs": boroughs,
        },
        "landMask": [[round_path(ring) for ring in polygon] for polygon in all_polygons],
        "externalLand": external_land,
        "parks": parks,
        "streets": streets,
        "routes": route_shapes,
        "stations": [
            {
                "id": station["id"],
                "name": station["name"],
                "point": round_point(station["point"]),
                "insideGla": station["insideGla"],
                "routes": sorted(station["routes"]),
                "zones": station.get("zones"),
            }
            for station in stations
        ],
        "routeStates": route_states,
        "stationStates": station_states,
        "routeWaits": route_waits,
        "adjacency": adjacency,
        "cells": cells,
        "mask": mask,
        "routeStyles": route_styles,
    }

    SITE_DATA_PATH.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {SITE_DATA_PATH}")


if __name__ == "__main__":
    main()
