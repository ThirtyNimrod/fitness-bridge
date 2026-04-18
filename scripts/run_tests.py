import os
import re
import sys
import subprocess


def _parse_pytest_summary(output: str) -> dict:
    """
    Extract counts from pytest's final summary line, e.g.:
      '5 passed, 2 failed, 1 skipped, 1 error in 3.14s'
    Returns a dict with keys: passed, failed, skipped, error.
    """
    counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    # Match the last line that contains " passed" or " failed" etc.
    pattern = re.compile(r"(\d+)\s+(passed|failed|skipped|error)")
    for match in pattern.finditer(output):
        num, label = int(match.group(1)), match.group(2)
        if label in counts:
            counts[label] += num
    return counts


def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    phase_tests_dir = os.path.join(root_dir, "tests", "phase-tests")

    if not os.path.exists(phase_tests_dir):
        print(f"Error: Directory {phase_tests_dir} not found.")
        sys.exit(1)

    test_files = [
        f for f in os.listdir(phase_tests_dir)
        if f.startswith("test_phase") and f.endswith(".py")
    ]
    test_files.sort()

    if not test_files:
        print("No phase tests found!")
        sys.exit(1)

    print("=" * 60)
    print(" Fitness Bridge AI - Test Runner")
    print("=" * 60)
    print(f"Found {len(test_files)} phase test files to execute in sequence.\n")

    all_passed = True
    totals = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}

    for test_file in test_files:
        test_path = os.path.join("tests", "phase-tests", test_file)
        print(f"\n[{test_file}] Running...")

        # Capture output so we can parse counts, but also stream it live.
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-v", "--disable-warnings"],
            cwd=root_dir,
            capture_output=True,
            text=True,
        )

        # Stream captured output to the terminal.
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        # Accumulate counts from this phase.
        phase_counts = _parse_pytest_summary(result.stdout)
        for key in totals:
            totals[key] += phase_counts[key]

        if result.returncode != 0:
            print(f"\n❌ FAILED: {test_file}")
            all_passed = False
            break  # Stop on first phase failure
        else:
            print(f"✅ PASSED: {test_file}")

    # ── Grand Total Summary ─────────────────────────────────────────────────
    total_ran = totals["passed"] + totals["failed"] + totals["skipped"] + totals["error"]
    print("\n" + "=" * 60)
    print(" TEST RUN SUMMARY")
    print("=" * 60)
    print(f"  Total ran : {total_ran}")
    print(f"  ✅ Passed  : {totals['passed']}")
    print(f"  ❌ Failed  : {totals['failed']}")
    print(f"  ⏭  Skipped : {totals['skipped']}")
    if totals["error"]:
        print(f"  💥 Errors  : {totals['error']}")
    print("=" * 60)

    if all_passed:
        print("🎉 ALL PHASE TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("💥 TEST SUITE FAILED. Stopping execution.")
        sys.exit(1)


if __name__ == "__main__":
    main()
