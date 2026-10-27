"""Run every current test suite sequentially against disposable Oracle.

Requires the dedicated container documented in tests/CHECKLIST_FINDINGS.md.
Run: RUN_MANUAL_CHECKLIST=1 ORACLE_PORT=1522 PYTHONDONTWRITEBYTECODE=1
     .venv/bin/python -m tests.run_all_tests --single-user
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import oracledb


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests"
SUITES = [
    ("Full checklist", ["-m", "tests.run_manual_checklist"], "all_checklist.log"),
    ("Discovered regression suite", ["-m", "unittest", "discover", "-s", "tests", "-v"], "all_regressions.log"),
    ("Restore integration verification", ["-m", "tests.run_restore_verification"], "all_restore.log"),
    ("Selector integration verification", ["-m", "tests.run_selector_verification"], "all_selectors.log"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--single-user", action="store_true",
                        help="Assume one active session with sequential operations; skip concurrency tests")
    args = parser.parse_args()
    if os.environ.get("RUN_MANUAL_CHECKLIST") != "1" or os.environ.get("ORACLE_PORT") != "1522":
        raise RuntimeError("Explicit test opt-in and disposable Oracle port 1522 are required")
    environment = dict(os.environ, ORACLE_HOST="localhost", ORACLE_PORT="1522",
                       ORACLE_SERVICE="FREEPDB1", ORACLE_USER="concordance",
                       ORACLE_PASSWORD="songsproject", RUN_ORACLE_INTEGRATION="1",
                       PYTHONDONTWRITEBYTECODE="1",
                       SINGLE_USER_TESTS="1" if args.single_user else "0")
    scope = ("One active user session, with sequential operations; concurrency tests are out of scope."
             if args.single_user else "All scenarios, including concurrent operations.")
    deadline = time.monotonic() + 120
    print("Waiting for disposable Oracle on localhost:1522", flush=True)
    while True:
        try:
            with oracledb.connect(user="concordance", password="songsproject",
                                  dsn="localhost:1522/FREEPDB1", tcp_connect_timeout=3):
                break
        except oracledb.Error:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)

    results = []
    for name, arguments, filename in SUITES:
        print(f"Running {name}", flush=True)
        started = time.monotonic()
        path = OUT / filename
        with path.open("w") as log:
            process = subprocess.run([sys.executable, *arguments], cwd=ROOT, env=environment,
                                     stdout=log, stderr=subprocess.STDOUT)
        output = path.read_text()
        totals = re.findall(r"^Ran (\d+) tests? in", output, re.MULTILINE)
        summaries = re.findall(r"^(?:FAILED|OK).*", output, re.MULTILINE)
        summary = summaries[-1] if summaries else "No unittest summary"
        result = {"suite": name, "exit_code": process.returncode,
                  "seconds": round(time.monotonic() - started, 3),
                  "tests": int(totals[-1]) if totals else None,
                  "failures": 0, "errors": 0, "skipped": 0,
                  "log": str(path), "summary": summary}
        for category in ("failures", "errors", "skipped"):
            match = re.search(rf"{category}=(\d+)", summary)
            result[category] = int(match[1]) if match else 0
        result["passed"] = (result["tests"] - result["failures"] - result["errors"] - result["skipped"]
                            if result["tests"] is not None else None)
        result["failed_cases"] = re.findall(r"^(?:FAIL|ERROR): (.+)$", output, re.MULTILINE)
        result["skipped_cases"] = re.findall(r"^test_.* \.\.\. skipped .+$", output, re.MULTILINE)
        results.append(result)
        print(f"{name}: {result['tests']} tests; {summary}", flush=True)

    report = {"executed_at": datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
              "database": "Disposable Oracle, localhost:1522/FREEPDB1", "scope": scope,
              "suites": results}
    (OUT / "all_test_results.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Latest complete test run", "", f"Executed: {report['executed_at']}", "",
             f"Scope: {scope}", "",
             "Real Oracle on isolated port 1522; existing database on port 1521 was not used.", "",
             "| Suite | Tests | Passed | Failures | Errors | Skipped |",
             "|---|---:|---:|---:|---:|---:|"]
    for result in results:
        lines.append(f"| {result['suite']} | {result['tests']} | {result['passed']} | "
                     f"{result['failures']} | {result['errors']} | {result['skipped']} |")
    lines += ["", "The dedicated restore and selector suites repeat some checklist coverage and add targeted verification; suite counts are executions, not a count of unique scenarios.",
              "", "## Failures and logs", ""]
    for result in results:
        lines.append(f"- [{result['suite']}]({result['log']}): {result['summary']}.")
        for failed in result["failed_cases"]:
            lines.append(f"  - `{failed}`")
        for skipped in result["skipped_cases"]:
            lines.append(f"  - Out of scope: `{skipped}`")
    lines += ["", "## Current checklist evidence", ""]
    checklist = json.loads((OUT / "checklist_results.json").read_text())
    for test in ("test_BB24_search_state_after_restore", "test_BB26_same_name_different_albums", "test_WB14_concurrency_races"):
        record = next(row for row in checklist["results"] if row["test"] == test)
        lines += [f"**{test}: {record['status']}**", ""]
        if record["status"] == "SKIP":
            lines += [record["detail"], ""]
        else:
            lines += ["```json", json.dumps(checklist["observations"].get(test, {}), indent=2), "```", ""]
    (OUT / "LATEST_TEST_RESULTS.md").write_text("\n".join(lines) + "\n")
    return int(any(result["exit_code"] for result in results))


if __name__ == "__main__":
    sys.exit(main())
