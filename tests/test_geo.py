from __future__ import annotations

from app.geo import GeoRegion, _point_in_polygon


def test_point_in_polygon_simple_square() -> None:
    square = (
        (0.0, 0.0),
        (0.0, 1.0),
        (1.0, 1.0),
        (1.0, 0.0),
    )
    assert _point_in_polygon((0.5, 0.5), square) is True
    assert _point_in_polygon((1.5, 0.5), square) is False


def test_geo_region_contains() -> None:
    region = GeoRegion(
        name='square',
        polygons=(
            (
                (0.0, 0.0),
                (0.0, 1.0),
                (1.0, 1.0),
                (1.0, 0.0),
            ),
        ),
    )
    assert region.contains(lat=0.5, lon=0.5) is True
    assert region.contains(lat=2.0, lon=2.0) is False
