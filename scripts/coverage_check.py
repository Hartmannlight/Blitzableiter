from __future__ import annotations

import subprocess
import sys


def main() -> int:
    run_cmd = [sys.executable, '-m', 'coverage', 'run', '-m', 'pytest']
    result = subprocess.run(run_cmd)
    if result.returncode != 0:
        return result.returncode

    report_cmd = [sys.executable, '-m', 'coverage', 'report', '--fail-under', '85']
    return subprocess.run(report_cmd).returncode


if __name__ == '__main__':
    raise SystemExit(main())
