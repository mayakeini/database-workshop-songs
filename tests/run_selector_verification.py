"""Recheck song selectors and related filters against disposable Oracle.

Requires the environment documented in tests/CHECKLIST_FINDINGS.md. Run with:
RUN_MANUAL_CHECKLIST=1 ORACLE_PORT=1522 PYTHONDONTWRITEBYTECODE=1
    .venv/bin/python -m tests.run_selector_verification
"""
import json
import sys
import unittest

from src import db
from tests.checklist_support import TESTS, metrics, page, run, song_id, upload
from tests.run_manual_checklist import Checklist, RecordingResult


class SelectorVerification(Checklist):
    baseline = (TESTS / "checklist_baseline.xml").read_bytes()
    observations = {}

    @classmethod
    def tearDownClass(cls):
        db.get_database_service().close()
        db.get_database_service.clear()

    def test_album_selection_returns_each_songs_data(self):
        # Use two existing files with distinct counts under matching metadata to
        # prove that selecting an album retrieves that record, not its namesake.
        first_id = song_id("Example")
        app = upload(2, title="Example", artist="Test Artist", album="Other Album")
        self.assert_ui_ok(app)
        second_id = app.session_state["uploaded_song_id"]
        for path in ("pages/3_word_index.py", "pages/6_statistics.py"):
            app = page(path)
            for selected_id, expected_words in ((first_id, 16), (second_id, 367)):
                selector = app.selectbox[0]
                label = next(option for option in selector.options if f"ID: {selected_id})" in option)
                selector.select(label)
                run(app)
                self.assert_ui_ok(app)
                if path.endswith("3_word_index.py"):
                    self.assertEqual(len(app.dataframe[0].value), expected_words)
                else:
                    self.assertEqual(metrics(app)["Words"], str(expected_words))
        self.note(selected_song_counts={str(first_id): 16, str(second_id): 367})


if __name__ == "__main__":
    names = ["test_BB14_index_csv", "test_BB15_group_index_filters", "test_BB21_statistics",
             "test_BB26_same_name_different_albums", "test_album_selection_returns_each_songs_data"]
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(
        unittest.TestSuite(SelectorVerification(name) for name in names))
    report = {"tests_run": result.testsRun, "failures": len(result.failures),
              "errors": len(result.errors), "results": result.records,
              "observations": SelectorVerification.observations}
    (TESTS / "selector_verification_results.json").write_text(json.dumps(report, indent=2) + "\n")
    sys.exit(0 if result.wasSuccessful() else 1)
