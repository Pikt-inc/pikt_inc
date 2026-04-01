from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_TESTS = [
    "pikt_inc/tests/test_building_sop.py",
    "pikt_inc/tests/test_customer_portal.py",
    "pikt_inc/tests/test_page_views.py",
]

DISPATCH_TESTS = [
    "pikt_inc/tests/test_dispatch_phase1.py",
    "pikt_inc/tests/test_dispatch_phase2.py",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the focused Building SOP regression and flake-detection suite."
    )
    parser.add_argument(
        "--loops",
        type=int,
        default=1,
        help="Number of times to run the selected suite. Defaults to 1.",
    )
    parser.add_argument(
        "--include-dispatch",
        action="store_true",
        help="Include dispatch regression files that exercise SSR snapshot side effects.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue running all loops after a failure. Default behavior stops on first failure.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter used to invoke pytest. Defaults to the current interpreter.",
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        help="Optional explicit test files to run instead of the default SOP suite.",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional pytest arguments. Pass them after '--', for example: -- -k building_sop -q",
    )
    return parser.parse_args()


def build_targets(args: argparse.Namespace) -> list[str]:
    if args.tests:
        return list(args.tests)

    targets = list(DEFAULT_TESTS)
    if args.include_dispatch:
        targets.extend(DISPATCH_TESTS)
    return targets


def normalize_pytest_args(raw_args: list[str]) -> list[str]:
    if raw_args and raw_args[0] == "--":
        return raw_args[1:]
    return list(raw_args)


def format_seconds(duration: float) -> str:
    return f"{duration:.2f}s"


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    loops = max(1, int(args.loops or 1))
    targets = build_targets(args)
    pytest_args = normalize_pytest_args(args.pytest_args)

    print("Building SOP stress suite")
    print(f"Workdir: {repo_root}")
    print(f"Loops: {loops}")
    print(f"Targets: {', '.join(targets)}")
    if pytest_args:
        print(f"Pytest args: {' '.join(pytest_args)}")

    run_durations: list[float] = []
    failed_runs: list[int] = []

    for index in range(1, loops + 1):
        cmd = [args.python, "-m", "pytest", *targets, *pytest_args]
        print(f"\n[{index}/{loops}] Running: {' '.join(cmd)}")
        started = time.perf_counter()
        completed = subprocess.run(cmd, cwd=repo_root, check=False)
        duration = time.perf_counter() - started
        run_durations.append(duration)
        passed = completed.returncode == 0
        status = "PASS" if passed else "FAIL"
        print(f"[{index}/{loops}] {status} in {format_seconds(duration)}")

        if not passed:
            failed_runs.append(index)
            if not args.keep_going:
                break

    executed = len(run_durations)
    passed_runs = executed - len(failed_runs)
    average = statistics.mean(run_durations) if run_durations else 0.0
    slowest = max(run_durations) if run_durations else 0.0

    print("\nSummary")
    print(f"Executed: {executed}")
    print(f"Passed: {passed_runs}")
    print(f"Failed: {len(failed_runs)}")
    print(f"Average duration: {format_seconds(average)}")
    print(f"Slowest duration: {format_seconds(slowest)}")
    if failed_runs:
        print(f"Failed runs: {', '.join(str(index) for index in failed_runs)}")

    return 0 if not failed_runs else 1


if __name__ == "__main__":
    raise SystemExit(main())
