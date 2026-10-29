"""Transaction and interactive UI regression tests for individual song deletion."""

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

from src import db, song_service

ROOT = Path(__file__).resolve().parents[1]


class DeleteSongServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.connection.__enter__.return_value = self.connection
        self.cursor = self.connection.cursor.return_value
        self.cursor.__enter__.return_value = self.cursor
        pool = MagicMock()
        pool.acquire.return_value = self.connection
        service = db.DatabaseService(pool)
        patcher = patch.object(song_service, "get_database_service", return_value=service)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_delete_targets_one_bound_id_and_commits_once(self):
        self.cursor.rowcount = 1
        self.assertTrue(song_service.delete_song(42))
        self.cursor.execute.assert_called_once()
        sql = " ".join(self.cursor.execute.call_args.args[0].split())
        self.assertEqual(sql, "DELETE FROM songs WHERE song_id = :song_id")
        self.assertEqual(self.cursor.execute.call_args.kwargs, {"song_id": 42})
        self.connection.commit.assert_called_once_with()
        self.connection.rollback.assert_not_called()
        self.connection.__exit__.assert_called_once()

    def test_missing_song_returns_false(self):
        self.cursor.rowcount = 0
        self.assertFalse(song_service.delete_song(42))
        self.connection.commit.assert_called_once_with()
        self.connection.rollback.assert_not_called()

    def test_failure_rolls_back_and_propagates(self):
        self.cursor.execute.side_effect = RuntimeError("database unavailable")
        with self.assertLogs("src.song_service", level="ERROR"):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                song_service.delete_song(42)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once_with()
        self.connection.__exit__.assert_called_once()


class DeleteSongPageTests(unittest.TestCase):
    def setUp(self):
        # Duplicate names must still have independent controls and deletion IDs.
        self.songs = [
            {"song_id": song_id, "title": 'A "Song"', "artist": "Artist's Name",
             "album": album, "publication_year": 2020, "stanzas": 1, "lines": 1, "words": 2}
            for song_id, album in ((11, "First Album"), (22, "Second Album"))
        ]
        list_patcher = patch.object(song_service, "get_all_songs_with_counts", side_effect=lambda: list(self.songs))
        delete_patcher = patch.object(song_service, "delete_song", side_effect=self.delete_fixture_song)
        self.load_songs = list_patcher.start()
        self.delete_song = delete_patcher.start()
        self.addCleanup(list_patcher.stop)
        self.addCleanup(delete_patcher.stop)
        self.app = AppTest.from_file(str(ROOT / "pages" / "9_delete_song.py"))

    def delete_fixture_song(self, song_id):
        before = len(self.songs)
        self.songs[:] = [song for song in self.songs if song["song_id"] != song_id]
        return len(self.songs) < before

    def run_page(self):
        self.app.run()
        self.assertEqual(len(self.app.exception), 0)

    def click(self, key):
        self.app.button(key=key).click()
        self.run_page()

    def button_keys(self):
        return [button.key for button in self.app.button]

    def test_list_and_open_confirmation_do_not_delete(self):
        self.run_page()
        self.assertEqual(self.app.title[0].value, "Delete Song")
        self.assertEqual(self.button_keys(), ["delete_song_11", "delete_song_22"])
        self.assertTrue(any("First Album" in caption.value for caption in self.app.caption))
        self.assertTrue(any("Second Album" in caption.value for caption in self.app.caption))
        self.click("delete_song_22")
        self.assertIn('Are you sure you want to delete "A "Song"" by Artist\'s Name?',
                      [text.value for text in self.app.text])
        self.assertIn("confirm_delete_song_22", self.button_keys())
        self.assertNotIn("confirm_delete_song_11", self.button_keys())
        self.delete_song.assert_not_called()

    def test_no_cancels_without_changing_data(self):
        self.run_page()
        self.click("delete_song_11")
        self.click("cancel_delete_song_11")
        self.assertEqual(self.button_keys(), ["delete_song_11", "delete_song_22"])
        self.delete_song.assert_not_called()
        self.assertEqual(len(self.songs), 2)

    def test_switching_rows_keeps_only_one_confirmation(self):
        self.run_page()
        self.click("delete_song_11")
        self.click("delete_song_22")
        self.assertNotIn("confirm_delete_song_11", self.button_keys())
        self.assertIn("confirm_delete_song_22", self.button_keys())
        self.delete_song.assert_not_called()

    def test_yes_deletes_selected_id_and_keeps_notice_after_refresh(self):
        self.run_page()
        self.click("delete_song_22")
        self.click("confirm_delete_song_22")
        self.delete_song.assert_called_once_with(22)
        self.assertEqual(self.button_keys(), ["delete_song_11"])
        self.assertEqual(len(self.app.success), 1)
        self.assertIn("Artist's Name", self.app.success[0].value)
        self.run_page()
        self.delete_song.assert_called_once_with(22)
        self.assertEqual(len(self.app.success), 0)

    def test_deleting_last_song_shows_empty_state(self):
        self.songs[:] = self.songs[:1]
        self.run_page()
        self.click("delete_song_11")
        self.click("confirm_delete_song_11")
        self.assertEqual(self.button_keys(), [])
        self.assertEqual(self.app.info[0].value, "No songs have been uploaded yet.")
        self.assertEqual(len(self.app.success), 1)

    def test_empty_collection_has_no_delete_controls(self):
        self.songs.clear()
        self.run_page()
        self.assertEqual(self.button_keys(), [])
        self.assertEqual(len(self.app.info), 1)

    def test_song_removed_by_another_session_before_confirmation(self):
        self.run_page()
        self.click("delete_song_11")
        self.songs.pop(0)
        self.click("confirm_delete_song_11")
        self.assertEqual(self.app.warning[0].value, "This song no longer exists.")
        self.assertEqual(self.button_keys(), ["delete_song_22"])
        self.delete_song.assert_not_called()

    def test_song_disappearing_between_list_and_delete_refreshes_with_warning(self):
        self.run_page()
        self.click("delete_song_11")

        def already_deleted(song_id):
            self.delete_fixture_song(song_id)
            return False

        self.delete_song.side_effect = already_deleted
        self.click("confirm_delete_song_11")
        self.assertEqual(self.app.warning[0].value, "This song no longer exists.")
        self.assertEqual(self.button_keys(), ["delete_song_22"])

    def test_delete_error_retains_confirmation_and_can_be_retried(self):
        self.run_page()
        self.click("delete_song_11")
        self.delete_song.side_effect = RuntimeError("database unavailable")
        self.click("confirm_delete_song_11")
        self.assertEqual(self.app.error[0].value, "Could not delete the song. Please try again.")
        self.assertIn("confirm_delete_song_11", self.button_keys())
        self.assertEqual(len(self.songs), 2)
        self.delete_song.side_effect = self.delete_fixture_song
        self.click("confirm_delete_song_11")
        self.assertEqual(self.button_keys(), ["delete_song_22"])

    def test_load_error_has_no_delete_controls(self):
        self.load_songs.side_effect = RuntimeError("database unavailable")
        self.run_page()
        self.assertEqual(self.button_keys(), [])
        self.assertEqual(self.app.error[0].value, "Could not load the song collection. Please try again.")
        self.delete_song.assert_not_called()

    def test_deletion_clears_cached_search_and_matching_upload_receipt(self):
        self.app.session_state["word_search_results"] = [(1, 11)]
        self.app.session_state["word_occurrence_index"] = 2
        self.app.session_state["word_search_error"] = "Old error"
        self.app.session_state["uploaded_song_id"] = 11
        self.app.session_state["song_uploaded_successfully"] = True
        self.app.session_state["uploaded_song_summary"] = {"words": 2}
        self.app.session_state["file_uploader_key"] = 3
        self.run_page()
        self.click("delete_song_11")
        self.click("confirm_delete_song_11")
        state = self.app.session_state
        self.assertIsNone(state["word_search_results"])
        self.assertEqual(state["word_occurrence_index"], 0)
        self.assertIsNone(state["word_search_error"])
        self.assertIsNone(state["uploaded_song_id"])
        self.assertFalse(state["song_uploaded_successfully"])
        self.assertIsNone(state["uploaded_song_summary"])
        self.assertEqual(state["file_uploader_key"], 4)

    def test_deletion_preserves_another_songs_upload_receipt(self):
        self.app.session_state["uploaded_song_id"] = 22
        self.app.session_state["song_uploaded_successfully"] = True
        self.app.session_state["uploaded_song_summary"] = {"words": 2}
        self.run_page()
        self.click("delete_song_11")
        self.click("confirm_delete_song_11")
        self.assertEqual(self.app.session_state["uploaded_song_id"], 22)
        self.assertTrue(self.app.session_state["song_uploaded_successfully"])
        self.assertEqual(self.app.session_state["uploaded_song_summary"], {"words": 2})


if __name__ == "__main__":
    unittest.main()
