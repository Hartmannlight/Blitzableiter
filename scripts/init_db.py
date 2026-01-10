from __future__ import annotations

import os
import sys

from app.db import PostgresRepository


def main() -> None:
    dsn = os.getenv('BLITZ_DATABASE_URL') or os.getenv('DATABASE_URL')
    if not dsn:
        print('Set BLITZ_DATABASE_URL or DATABASE_URL first', file=sys.stderr)
        sys.exit(1)
    try:
        PostgresRepository(dsn)
    except Exception as exc:  # noqa: BLE001
        print(f'Failed to initialize database: {exc}', file=sys.stderr)
        sys.exit(1)
    print('Database schema ensured')


if __name__ == '__main__':
    main()
