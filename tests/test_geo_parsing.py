from __future__ import annotations

import json

import pytest

from app.geo import GeoRegion, _extract_polygons, _point_in_polygon, load_geojson_regions
from tests.helpers import make_test_dir


def test_load_geojson_regions_multipolygon() -> None:
    tmp = make_test_dir()
    path = tmp / 'multi.geojson'
    payload = {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {'name': 'multi'},
                'geometry': {
                    'type': 'MultiPolygon',
                    'coordinates': [
                        [[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.0, 0.0]]],
                        [[[2.0, 2.0], [2.0, 3.0], [3.0, 3.0], [2.0, 2.0]]],
                    ],
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding='utf-8')

    regions = load_geojson_regions(path)
    assert len(regions) == 1
    region = regions[0]
    assert isinstance(region, GeoRegion)
    assert region.bounding_box == (0.0, 0.0, 3.0, 3.0)


def test_load_geojson_regions_from_geometry_root() -> None:
    tmp = make_test_dir()
    path = tmp / 'geom.geojson'
    payload = {
        'type': 'Polygon',
        'coordinates': [[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.0, 0.0]]],
    }
    path.write_text(json.dumps(payload), encoding='utf-8')

    regions = load_geojson_regions(path)
    assert len(regions) == 1
    assert regions[0].name == 'feature_0'


def test_point_in_polygon_rejects_short_ring() -> None:
    assert _point_in_polygon((0.0, 0.0), ((0.0, 0.0), (1.0, 1.0))) is False


def test_extract_polygons_invalid_inputs() -> None:
    assert _extract_polygons({'type': 'Polygon', 'coordinates': []}) == ()
    assert _extract_polygons({'type': 'Polygon', 'coordinates': [['a', 'b']]}) == ()
    assert _extract_polygons({'type': 'MultiPolygon', 'coordinates': [[]]}) == ()
    assert _extract_polygons({'type': 'Unknown', 'coordinates': []}) == ()


def test_load_geojson_missing_file_raises() -> None:
    tmp = make_test_dir()
    path = tmp / 'missing.geojson'
    with pytest.raises(FileNotFoundError):
        load_geojson_regions(path)
