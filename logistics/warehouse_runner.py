"""Phase 5 bounded-retry warehouse build, followed by a strict offline quality gate."""
from __future__ import annotations

import argparse
import time
from typing import Callable, TypeVar

from .quality_monitor import run_quality_check

T = TypeVar('T')


def is_transient(exc: Exception) -> bool:
    # Do not retry missing input files, corrupt source data, bad schemas or failed checks.
    if isinstance(exc, FileNotFoundError):
        return False
    if isinstance(exc, OSError):
        return True
    message = str(exc).lower()
    return any(phrase in message for phrase in (
        'could not set lock', 'database is locked',
        'resource temporarily unavailable', 'temporarily unavailable',
    ))


def with_retry(action: Callable[[], T], max_attempts: int = 3,
               delay_seconds: float = 1.0, sleep: Callable[[float], None] = time.sleep) -> T:
    if max_attempts < 1 or delay_seconds < 0:
        raise ValueError('max_attempts must be >= 1 and delay_seconds must be >= 0')
    for attempt in range(1, max_attempts + 1):
        try:
            return action()
        except Exception as exc:
            if attempt == max_attempts or not is_transient(exc):
                raise
            pause = delay_seconds * (2 ** (attempt - 1))
            print(f'Transient warehouse error, attempt {attempt}/{max_attempts}: {exc}')
            print(f'Retrying in {pause:g} seconds')
            sleep(pause)
    raise AssertionError('unreachable')


def main() -> None:
    parser = argparse.ArgumentParser(description='Rebuild local DuckDB and enforce quality gate')
    parser.add_argument('--max-attempts', type=int, default=3)
    parser.add_argument('--retry-delay', type=float, default=1.0)
    args = parser.parse_args()
    from .warehouse import build_warehouse
    try:
        result = with_retry(build_warehouse, args.max_attempts, args.retry_delay)
    except Exception as exc:
        print(f'WAREHOUSE BUILD FAILED ({type(exc).__name__}): {exc}')
        raise SystemExit(1) from exc
    print(f'WAREHOUSE BUILD PASS: {result["fact_shipment_rows"]} shipment rows')
    report = run_quality_check()
    print(f'QUALITY GATE: {report["status"]}')
    for reason in report['failures']:
        print(f'  FAIL: {reason}')
    raise SystemExit(0 if report['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
