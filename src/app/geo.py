from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class GeoRegion:
    name: str
    polygons: tuple[tuple[tuple[float, float], ...], ...]

    @property
    def bounding_box(self) -> tuple[float, float, float, float]:
        latitudes: list[float] = []
        longitudes: list[float] = []
        for poly in self.polygons:
            for lon, lat in poly:
                longitudes.append(float(lon))
                latitudes.append(float(lat))
        return (
            min(latitudes),
            min(longitudes),
            max(latitudes),
            max(longitudes),
        )

    def contains(self, lat: float, lon: float) -> bool:
        point = (float(lon), float(lat))
        for polygon in self.polygons:
            if _point_in_polygon(point, polygon):
                return True
        return False


def _point_in_polygon(point: tuple[float, float], polygon: tuple[tuple[float, float], ...]) -> bool:
    # Ray casting algorithm, ignores holes but fast enough for our use case.
    x, y = point
    inside = False
    if len(polygon) < 3:
        return False

    for i in range(len(polygon)):
        x1, y1 = polygon[i - 1]
        x2, y2 = polygon[i]
        intersects = ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1)
        if intersects:
            inside = not inside
    return inside


def _extract_polygons(geometry: dict[str, Any]) -> tuple[tuple[tuple[float, float], ...], ...]:
    geom_type = geometry.get('type')
    coords = geometry.get('coordinates')
    if geom_type == 'Polygon':
        rings = coords or []
        if not rings:
            return ()
        try:
            polygon = tuple((float(lon), float(lat)) for lon, lat in rings[0])
            return (polygon,)
        except (TypeError, ValueError):
            return ()
    if geom_type == 'MultiPolygon':
        polygons: list[tuple[tuple[float, float], ...]] = []
        for poly in coords or []:
            if not poly:
                continue
            try:
                polygons.append(tuple((float(lon), float(lat)) for lon, lat in poly[0]))
            except (TypeError, ValueError, IndexError):
                continue
        return tuple(polygons)
    return ()


def _iter_features(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    if data.get('type') == 'FeatureCollection':
        for feature in data.get('features', []) or []:
            yield feature
        return
    if data.get('type') == 'Feature':
        yield data
        return
    # fallback: treat the document itself as geometry
    yield {'type': 'Feature', 'geometry': data}


def load_geojson_regions(path: Path) -> list[GeoRegion]:
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_text(encoding='utf-8')
    data = json.loads(raw)
    regions: list[GeoRegion] = []

    for idx, feature in enumerate(_iter_features(data)):
        geometry = feature.get('geometry') or {}
        polygons = _extract_polygons(geometry)
        if not polygons:
            continue
        name = feature.get('properties', {}).get('name') or f'feature_{idx}'
        regions.append(GeoRegion(name=name, polygons=polygons))

    return regions
