from __future__ import annotations

import json
from datetime import UTC

import pytest

from app.atudo_client import AtudoClient, BoundingBox, RawSnapshotStore, normalize_poi


def test_bounding_box_split_stays_within_bounds() -> None:
    bbox = BoundingBox(south=0.0, west=0.0, north=2.0, east=2.0)
    tiles = bbox.split(max_size=1.0)

    assert len(tiles) == 9
    assert tiles[0].south >= 0.0
    assert tiles[0].west >= 0.0
    assert tiles[-1].north <= 2.0
    assert tiles[-1].east <= 2.0


def test_build_url_includes_box_types_and_zoom() -> None:
    client = AtudoClient(fetcher=lambda url: url.encode('utf-8'))
    bbox = BoundingBox(south=1.0, west=2.0, north=3.0, east=4.0)
    url = client._build_url(bbox=bbox, poi_types=('1', 'vwd'), zoom=15)

    assert 'box=1.0%2C2.0%2C3.0%2C4.0' in url
    assert 'type=1%2Cvwd' in url
    assert 'z=15' in url


def test_fetch_parses_response_and_sets_metadata() -> None:
    payload = {'pois': [{'id': 'p1', 'lat': '1.0', 'lng': '2.0', 'type': '1'}]}

    def fake_fetcher(url: str) -> bytes:  # noqa: ARG001
        return json.dumps(payload).encode('utf-8')

    client = AtudoClient(fetcher=fake_fetcher)
    bbox = BoundingBox(south=1.0, west=2.0, north=3.0, east=4.0)
    response = client.fetch(bbox=bbox, poi_types=('1',), zoom=14)

    assert response.request_key == '1.0,2.0,3.0,4.0|z=14'
    assert response.response_body == payload
    assert response.requested_at.tzinfo == UTC
    assert response.pois()[0]['id'] == 'p1'


def test_fetch_raises_for_invalid_json() -> None:
    client = AtudoClient(fetcher=lambda url: b'not-json')  # noqa: ARG005
    bbox = BoundingBox(south=0.0, west=0.0, north=1.0, east=1.0)

    with pytest.raises(json.JSONDecodeError):
        client.fetch(bbox=bbox, poi_types=('1',), zoom=14)


def test_normalize_poi_handles_missing_fields() -> None:
    poi = normalize_poi({'lat': '1.0', 'lng': '2.0', 'type': '1', 'vmax': ''})

    assert poi.source == 'blitzer_de'
    assert poi.source_poi_id == 'unknown'
    assert poi.vmax is None
    assert poi.address == {}


def test_raw_snapshot_store_dedupes() -> None:
    store = RawSnapshotStore()
    payload = {'pois': []}
    client = AtudoClient(fetcher=lambda url: json.dumps(payload).encode('utf-8'))  # noqa: ARG005
    bbox = BoundingBox(south=0.0, west=0.0, north=1.0, east=1.0)

    first = client.fetch(bbox=bbox, poi_types=('1',), zoom=14)
    second = client.fetch(bbox=bbox, poi_types=('1',), zoom=14)

    assert store.maybe_store(first) is True
    assert store.maybe_store(second) is False
    assert len(store.snapshots) == 1
