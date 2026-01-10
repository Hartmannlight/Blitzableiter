from __future__ import annotations

import urllib.error

import pytest

from app.atudo_client import AtudoClient, AtudoResponse, BoundingBox, normalize_poi


class _FakeResponse:
    def read(self) -> bytes:
        return b'{}'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_atudo_response_pois_returns_empty_for_non_list() -> None:
    response = AtudoResponse(
        request_key='k',
        requested_at=None,  # type: ignore[arg-type]
        response_body={'pois': 'nope'},
        raw_hash='h',
    )
    assert response.pois() == []


def test_fetch_raises_for_transport_error() -> None:
    def _boom(url: str) -> bytes:  # noqa: ARG001
        raise urllib.error.URLError('nope')

    client = AtudoClient(fetcher=_boom)
    bbox = BoundingBox(south=0.0, west=0.0, north=1.0, east=1.0)

    with pytest.raises(urllib.error.URLError):
        client.fetch(bbox=bbox, poi_types=('1',), zoom=14)


def test_default_fetcher_reads_body(monkeypatch) -> None:
    client = AtudoClient()
    monkeypatch.setattr('urllib.request.urlopen', lambda url, timeout=5.0: _FakeResponse())

    assert client._default_fetcher('http://example') == b'{}'


def test_normalize_poi_invalid_vmax() -> None:
    poi = normalize_poi({'lat': '1.0', 'lng': '2.0', 'type': '1', 'vmax': 'x'})
    assert poi.vmax is None
