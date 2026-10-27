"""Regression tests for selecting songs with identical titles and artists."""

from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src import group_service, search_service, statistics_service


ROOT = Path(__file__).resolve().parents[1]
# Include missing albums and identical album names: every database ID must remain
# selectable even if all displayed metadata happens to be the same.
SONGS = [
    (11, "Example", "Test Artist", None, 2000, "2000-01-01 12:00:00 +02:00"),
    (22, "Example", "Test Artist", "Other Album", 2000, "2000-01-01 12:00:00 +02:00"),
    (33, "Example", "Test Artist", "Other Album", 2000, "2000-01-01 12:00:00 +02:00"),
]


class SongSelectorTests(unittest.TestCase):
    def setUp(self):
        self.search = self.mock(search_service, "search_songs", return_value=list(SONGS))
        self.mock(group_service, "get_groups", return_value=[(7, "Selected Words")])
        self.index = self.mock(search_service, "get_word_index", side_effect=self.index_rows)
        self.mock(statistics_service, "get_database_summary", return_value={
            "song_count": 3, "total_words": 6, "unique_words": 1,
            "average_word_length": 4, "average_words_per_line": 2,
        })
        self.song_statistics = self.mock(statistics_service, "get_song_statistics", side_effect=lambda song_id: {
            "title": "Example", "stanza_count": 1, "line_count": 1,
            "word_count": self.word_count(song_id), "unique_word_count": 1, "average_word_length": 4,
        })
        self.frequent = self.mock(statistics_service, "get_most_frequent_words", return_value=[])
        self.rare = self.mock(statistics_service, "get_rarest_words", return_value=[])
        self.lengths = self.mock(statistics_service, "get_word_length_distribution", return_value=[])
        self.stanzas = self.mock(statistics_service, "get_words_per_stanza", return_value=[])

    def mock(self, module, name, **kwargs):
        patcher = patch.object(module, name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    @staticmethod
    def word_count(song_id):
        return {11: 1, 22: 2, 33: 3}[song_id]

    def index_rows(self, song_id=None, group_id=None):
        selected_ids = [song_id] if song_id is not None else [11, 22, 33]
        return [("love", sid, "Example", 1, 1, 1, position)
                for sid in selected_ids for position in range(1, self.word_count(sid) + 1)]

    def run_page(self, app):
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0)
        return app

    def page(self, filename):
        return self.run_page(AppTest.from_file(str(ROOT / "pages" / filename)))

    def song_labels(self, app):
        labels = app.selectbox[0].options[1:]
        self.assertEqual(len(labels), 3, "One dropdown choice is required for each database song")
        self.assertEqual(len(set(labels)), 3)
        self.assertIn("No album", next(label for label in labels if "ID: 11)" in label))
        self.assertTrue(all("Other Album" in label for label in labels if "ID: 11)" not in label))
        return {sid: next(label for label in labels if f"ID: {sid})" in label) for sid in (11, 22, 33)}

    def test_word_index_selects_each_song_and_returns_to_all(self):
        app = self.page("3_word_index.py")
        labels = self.song_labels(app)
        for sid, label in labels.items():
            app.selectbox[0].select(label)
            self.run_page(app)
            self.index.assert_called_with(song_id=sid, group_id=None)
            self.assertEqual(len(app.dataframe[0].value), self.word_count(sid))
            self.assertEqual(len(app.download_button), 1)
        app.selectbox[0].select("All Songs")
        self.run_page(app)
        self.index.assert_called_with(song_id=None, group_id=None)
        self.assertEqual(len(app.dataframe[0].value), 6)

    def test_word_index_keeps_group_filter_when_switching_albums(self):
        app = self.page("3_word_index.py")
        labels = self.song_labels(app)
        app.selectbox(key="index_group_filter").select("Selected Words")
        self.run_page(app)
        for sid, label in labels.items():
            app.selectbox[0].select(label)
            self.run_page(app)
            self.index.assert_called_with(song_id=sid, group_id=7)

    def test_statistics_selects_each_song_for_summary_and_all_charts(self):
        app = self.page("6_statistics.py")
        labels = self.song_labels(app)
        for sid, label in labels.items():
            app.selectbox[0].select(label)
            self.run_page(app)
            self.song_statistics.assert_called_with(song_id=sid)
            self.frequent.assert_called_with(limit=10, song_id=sid)
            self.rare.assert_called_with(limit=10, song_id=sid)
            self.lengths.assert_called_with(song_id=sid)
            self.stanzas.assert_called_with(song_id=sid)
            self.assertEqual(next(metric.value for metric in app.metric if metric.label == "Words"),
                             str(self.word_count(sid)))
        app.selectbox[0].select("Entire Database")
        self.run_page(app)
        self.frequent.assert_called_with(limit=10, song_id=None)
        self.lengths.assert_called_with(song_id=None)
        self.assertEqual(next(metric.value for metric in app.metric if metric.label == "Songs"), "3")

    def test_word_index_empty_collection_keeps_all_songs_option(self):
        self.search.return_value = []
        self.index.side_effect = None
        self.index.return_value = []
        app = self.page("3_word_index.py")
        self.assertEqual(app.selectbox[0].options, ["All Songs"])
        self.index.assert_called_with(song_id=None, group_id=None)
        self.assertIn("No words were found", app.info[0].value)

    def test_statistics_empty_collection_keeps_entire_database_option(self):
        self.search.return_value = []
        app = self.page("6_statistics.py")
        self.assertEqual(app.selectbox[0].options, ["Entire Database"])
        self.song_statistics.assert_not_called()


if __name__ == "__main__":
    unittest.main()
