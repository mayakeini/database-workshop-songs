"""Regression tests for cached word searches across XML restore in one session."""

from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src import search_service, xml_service


ROOT = Path(__file__).resolve().parents[1]
RESTORED_COUNTS = {
    "songs": 1, "stanzas": 2, "words": 13, "word_occurrences": 16,
    "word_groups": 0, "group_words": 0, "phrases": 0, "phrase_occurrences": 0,
}
OLD_RESULTS = [
    (8, 1, "Example", "Test Artist", 2, 3, 1, 1, 8, "Love"),
    (14, 1, "Example", "Test Artist", 2, 4, 2, 2, 14, "love"),
]


class RestoreSearchStateTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(xml_service, "restore_database_from_xml", return_value=RESTORED_COUNTS)
        self.restore = patcher.start()
        self.addCleanup(patcher.stop)

    def run_page(self, app):
        app.run()
        self.assertEqual(len(app.exception), 0)
        return app

    def prepared_restore(self):
        app = AppTest.from_file(str(ROOT / "pages/7_backup_restore.py"))
        app.session_state["word_search_results"] = list(OLD_RESULTS)
        app.session_state["word_occurrence_index"] = 1
        app.session_state["word_search_error"] = "Previous search error"
        self.run_page(app)
        app.file_uploader[0].set_value(("backup.xml", b"<concordance_backup/>", "application/xml"))
        app.checkbox(key="confirm_xml_restore").check()
        return self.run_page(app)

    def submit_restore(self, app):
        app.button(key="restore_database_button").click()
        return self.run_page(app)

    def assert_search_preserved(self, app):
        self.assertEqual(app.session_state["word_search_results"], OLD_RESULTS)
        self.assertEqual(app.session_state["word_occurrence_index"], 1)
        self.assertEqual(app.session_state["word_search_error"], "Previous search error")

    def test_success_clears_results_navigation_and_error(self):
        app = self.submit_restore(self.prepared_restore())
        self.restore.assert_called_once_with(xml_data=b"<concordance_backup/>")
        self.assertIsNone(app.session_state["word_search_results"])
        self.assertEqual(app.session_state["word_occurrence_index"], 0)
        self.assertIsNone(app.session_state["word_search_error"])
        self.assertEqual(app.success[0].value, "Database restored successfully.")

    def test_invalid_backup_preserves_search(self):
        self.restore.side_effect = ValueError("The uploaded file is not valid XML.")
        app = self.submit_restore(self.prepared_restore())
        self.assert_search_preserved(app)
        self.assertEqual(len(app.success), 0)
        self.assertIn("not valid XML", app.error[-1].value)

    def test_database_failure_preserves_search(self):
        self.restore.side_effect = RuntimeError("Restore rolled back")
        app = self.submit_restore(self.prepared_restore())
        self.assert_search_preserved(app)
        self.assertEqual(len(app.success), 0)
        self.assertIn("existing data was not changed", app.error[-1].value)

    def test_loading_restore_page_does_not_clear_search(self):
        app = self.prepared_restore()
        self.assert_search_preserved(app)
        self.restore.assert_not_called()

    def test_return_to_search_hides_old_results_and_new_search_uses_new_ids(self):
        restored_results = [
            (108, 101, "Example", "Test Artist", 2, 3, 1, 1, 8, "Love"),
            (114, 101, "Example", "Test Artist", 2, 4, 2, 2, 14, "love"),
        ]
        context = {3: (ROOT / "sample_songs/example.txt").read_text().splitlines()[3]}
        with patch.object(search_service, "search_songs", return_value=[]), \
             patch.object(search_service, "get_context", return_value=context), \
             patch.object(search_service, "search_word", side_effect=[OLD_RESULTS, restored_results]) as search:
            app = AppTest.from_file(str(ROOT / "app.py"))
            app.switch_page("pages/2_search.py")
            self.run_page(app)
            app.text_input(key="search_word").set_value("love")
            app.button(key="FormSubmitter:word_search_form-Search Word").click()
            self.run_page(app)
            app.button(key="word_occurrence_next").click()
            self.run_page(app)
            self.assertEqual(app.session_state["word_occurrence_index"], 1)

            app.switch_page("pages/7_backup_restore.py")
            self.run_page(app)
            app.file_uploader[0].set_value(("backup.xml", b"<concordance_backup/>", "application/xml"))
            app.checkbox(key="confirm_xml_restore").check()
            self.run_page(app)
            self.submit_restore(app)

            app.switch_page("pages/2_search.py")
            self.run_page(app)
            self.assertIsNone(app.session_state["word_search_results"])
            self.assertNotIn("word_occurrence_next", [button.key for button in app.button])
            self.assertEqual(search.call_count, 1)

            app.text_input(key="search_word").set_value("love")
            app.button(key="FormSubmitter:word_search_form-Search Word").click()
            self.run_page(app)
            self.assertEqual(app.session_state["word_search_results"], restored_results)
            self.assertEqual(app.session_state["word_occurrence_index"], 0)
            self.assertFalse(app.button(key="word_occurrence_next").disabled)
            self.assertTrue(app.button(key="word_occurrence_previous").disabled)


if __name__ == "__main__":
    unittest.main()
