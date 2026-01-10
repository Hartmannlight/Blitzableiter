from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.metrics import (
    mark_api_request_duration,
    mark_api_request_failure,
    mark_api_request_success,
    mark_raw_snapshot_stored,
)


AtudoFetcher = Callable[[str], bytes]


@dataclass(frozen=True)
class BoundingBox:
    south: float
    west: float
    north: float
    east: float

    def to_param(self) -> str:
        return f'{self.south},{self.west},{self.north},{self.east}'

    def split(self, max_size: float = 1.0) -> list['BoundingBox']:
        lat_span = self.north - self.south
        lon_span = self.east - self.west
        if lat_span <= max_size and lon_span <= max_size:
            return [self]

        lat_steps = max(1, int(lat_span // max_size) + 1)
        lon_steps = max(1, int(lon_span // max_size) + 1)
        boxes: list[BoundingBox] = []
        lat_step_size = lat_span / lat_steps
        lon_step_size = lon_span / lon_steps

        for i in range(lat_steps):
            for j in range(lon_steps):
                south = self.south + i * lat_step_size
                north = min(self.north, south + lat_step_size)
                west = self.west + j * lon_step_size
                east = min(self.east, west + lon_step_size)
                boxes.append(BoundingBox(south=south, west=west, north=north, east=east))
        return boxes


@dataclass(frozen=True)
class NormalizedPoi:
    source: str
    source_poi_id: str
    lat: float
    lng: float
    poi_type: str
    vmax: int | None
    address: dict[str, Any]
    create_date: str | None
    confirm_date: str | None
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class AtudoResponse:
    request_key: str
    requested_at: datetime
    response_body: dict[str, Any]
    raw_hash: str

    def pois(self) -> list[dict[str, Any]]:
        pois = self.response_body.get('pois') or []
        if isinstance(pois, list):
            return [p for p in pois if isinstance(p, dict)]
        return []


class AtudoClient:
    def __init__(
        self,
        base_url: str = 'https://cdn2.atudo.net/api/4.0/pois.php',
        fetcher: AtudoFetcher | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._base_url = base_url
        self._fetcher = fetcher or self._default_fetcher
        self._timeout = timeout

    def _default_fetcher(self, url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=self._timeout) as response:  # nosec B310
            return response.read()

    def _build_url(self, bbox: BoundingBox, poi_types: tuple[str, ...], zoom: int) -> str:
        params = {
            'type': ','.join(poi_types) if poi_types else 'ts,0,1,2,3,4,5,6,vwd',
            'z': str(zoom),
            'box': bbox.to_param(),
        }
        query = urllib.parse.urlencode(params)
        return f'{self._base_url}?{query}'

    def fetch(self, bbox: BoundingBox, poi_types: tuple[str, ...], zoom: int = 14) -> AtudoResponse:
        url = self._build_url(bbox, poi_types, zoom)
        started = time.perf_counter()
        try:
            body = self._fetcher(url)
            duration = time.perf_counter() - started
            mark_api_request_success(source='blitzer_de')
            mark_api_request_duration(source='blitzer_de', duration_seconds=duration)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            mark_api_request_failure(source='blitzer_de')
            raise

        try:
            response_body = json.loads(body.decode('utf-8', errors='replace'))
        except json.JSONDecodeError:
            mark_api_request_failure(source='blitzer_de')
            raise
        raw_hash = hashlib.sha256(json.dumps(response_body, sort_keys=True).encode('utf-8')).hexdigest()
        request_key = f'{bbox.to_param()}|z={zoom}'
        return AtudoResponse(
            request_key=request_key,
            requested_at=datetime.now(timezone.utc),
            response_body=response_body,
            raw_hash=raw_hash,
        )


def normalize_poi(raw: dict[str, Any]) -> NormalizedPoi:
    source_poi_id = str(raw.get('backend') or raw.get('id') or raw.get('content') or 'unknown')
    lat = float(raw.get('lat', 0.0))
    lng = float(raw.get('lng', 0.0))
    poi_type = str(raw.get('type') or raw.get('poi_type') or '').strip() or 'unknown'

    vmax_raw = raw.get('vmax')
    try:
        vmax = int(str(vmax_raw)) if vmax_raw not in {None, ''} else None
    except ValueError:
        vmax = None

    address = raw.get('address') if isinstance(raw.get('address'), dict) else {}

    return NormalizedPoi(
        source='blitzer_de',
        source_poi_id=source_poi_id,
        lat=lat,
        lng=lng,
        poi_type=poi_type,
        vmax=vmax,
        address=address,
        create_date=str(raw.get('create_date')) if raw.get('create_date') is not None else None,
        confirm_date=str(raw.get('confirm_date')) if raw.get('confirm_date') is not None else None,
        raw_payload=raw,
    )


class RawSnapshotStore:
    def __init__(self) -> None:
        self._latest_hash: dict[str, str] = {}
        self._snapshots: list[AtudoResponse] = []

    def maybe_store(self, response: AtudoResponse) -> bool:
        prev_hash = self._latest_hash.get(response.request_key)
        if prev_hash == response.raw_hash:
            return False
        self._latest_hash[response.request_key] = response.raw_hash
        self._snapshots.append(response)
        mark_raw_snapshot_stored(source='blitzer_de')
        return True

    @property
    def snapshots(self) -> list[AtudoResponse]:
        return list(self._snapshots)
