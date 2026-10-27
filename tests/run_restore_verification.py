"""Recheck the restore fix without rewriting the historical checklist report.

Requires the disposable environment documented in tests/CHECKLIST_FINDINGS.md.
Run with RUN_MANUAL_CHECKLIST=1 ORACLE_PORT=1522 PYTHONDONTWRITEBYTECODE=1
    .venv/bin/python -m tests.run_restore_verification
"""
import json
import sys
import unittest

from src import db
from tests.checklist_support import TESTS
from tests.run_manual_checklist import Checklist, RecordingResult


class RestoreVerification(Checklist):
    baseline = (TESTS / "checklist_baseline.xml").read_bytes()
    observations = {}

    @classmethod
    def tearDownClass(cls):
        db.get_database_service().close()
        db.get_database_service.clear()


if __name__ == "__main__":
    names = ["test_BB22_xml_round_trip", "test_BB23_invalid_backups",
             "test_BB24_search_state_after_restore"]
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(
        unittest.TestSuite(RestoreVerification(name) for name in names))
    report = {"tests_run": result.testsRun, "failures": len(result.failures),
              "errors": len(result.errors), "results": result.records,
              "observations": RestoreVerification.observations}
    (TESTS / "restore_verification_results.json").write_text(json.dumps(report, indent=2) + "\n")
    sys.exit(0 if result.wasSuccessful() else 1)
