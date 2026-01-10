from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.atudo_client import AtudoResponse
from app.blitz_service import BlitzableiterService


def _build_fake_response(
    lat: float,
    lng: float,
    poi_type: str,
    poi_id: str,
    vmax: int | None,
) -> dict[str, Any]:
    now_str = datetime.now(UTC).strftime('%d.%m.%Y')
    payload = {
        'pois': [
            {
                'backend': poi_id,
                'id': poi_id,
                'lat': f'{lat:.6f}',
                'lng': f'{lng:.6f}',
                'type': poi_type,
                'vmax': str(vmax) if vmax is not None else '',
                'address': {'city': 'simulated'},
                'create_date': now_str,
                'confirm_date': now_str,
                'info': {},
                'style': 1,
            }
        ],
        'grid': [],
        'infos': [],
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Inject a synthetic POI and run one service cycle.',
    )
    parser.add_argument(
        '--lat',
        type=float,
        required=True,
        help='Latitude inside your GeoJSON area',
    )
    parser.add_argument(
        '--lng',
        type=float,
        required=True,
        help='Longitude inside your GeoJSON area',
    )
    parser.add_argument(
        '--type',
        dest='poi_type',
        default='1',
        help='POI type (e.g., 1 for mobile speed trap, vwd for hazard)',
    )
    parser.add_argument('--id', dest='poi_id', default='simulated-1', help='POI identifier')
    parser.add_argument('--vmax', type=int, default=None, help='Speed limit if applicable')
    args = parser.parse_args()

    service = BlitzableiterService()

    def fake_fetch(bbox, poi_types, zoom: int = 14) -> AtudoResponse:  # noqa: ARG001
        body = _build_fake_response(args.lat, args.lng, args.poi_type, args.poi_id, args.vmax)
        raw_json = json.dumps(body, sort_keys=True)
        raw_hash = hashlib.sha256(raw_json.encode('utf-8')).hexdigest()
        return AtudoResponse(
            request_key='synthetic',
            requested_at=datetime.now(UTC),
            response_body=body,
            raw_hash=raw_hash,
        )

    service._client.fetch = fake_fetch  # type: ignore[attr-defined]
    service.run_cycle(now=datetime.now(UTC))
    print(
        'Synthetic POI processed. Check your sender channel for a '
        'notification and logs for details.',
    )


if __name__ == '__main__':
    main()
