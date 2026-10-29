"""Opt-in Oracle verification: temporary fixtures are always rolled back.

Run with RUN_ORACLE_INTEGRATION=1 against a running project database.
Existing song data is never deleted, and no schema changes are made.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from src import db, song_service
from src.queries import db_queries


@unittest.skipUnless(os.getenv("RUN_ORACLE_INTEGRATION") == "1", "Requires opt-in local Oracle connection")
class DeleteSongOracleTests(unittest.TestCase):
    def test_cascades_statistics_and_preservation_of_shared_data(self):
        service = db.get_database_service()
        self.addCleanup(db.get_database_service.clear)
        self.addCleanup(service.close)
        tables = ("songs", "stanzas", "words", "word_occurrences", "word_groups",
                  "group_words", "phrases", "phrase_occurrences")
        prefix = f"delete_test_{uuid4().hex}"

        with service.read_cursor() as cursor:
            def snapshot():
                result = {}
                for table in tables:
                    cursor.execute(f"SELECT * FROM {table} ORDER BY 1, 2")
                    result[table] = cursor.fetchall()
                return result

            def insert(table, id_column, **values):
                result = cursor.var(int)
                columns = ", ".join(values)
                binds = ", ".join(f":{column}" for column in values)
                cursor.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ({binds}) RETURNING {id_column} INTO :new_id",
                    **values, new_id=result,
                )
                return int(result.getvalue()[0])

            def count(table, column, value):
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = :value", value=value)
                return cursor.fetchone()[0]

            def summary():
                db_queries.query_select_database_summary(cursor)
                return cursor.fetchone()

            @contextmanager
            def fixture_transaction():
                # Exercise production deletion SQL on the fixture connection;
                # the outer finally rolls back both inserts and deletes.
                yield cursor

            original = snapshot()
            initial_summary = summary()
            try:
                song_ids = [insert(
                    "songs", "song_id", title=f"{prefix}_{number}", artist="Deletion test",
                    album=None, publication_year=2020, upload_date=datetime.now(timezone.utc),
                ) for number in (1, 2)]
                stanza_ids = [insert("stanzas", "stanza_id", song_id=song_id, stanza_number=1)
                              for song_id in song_ids]
                shared_word, target_word, unused_word = [
                    insert("words", "word_id", text=f"{prefix}_{suffix}")
                    for suffix in ("shared", "target", "unused")
                ]
                occurrence_ids = []
                for index, word_ids in enumerate(((shared_word, target_word), (shared_word,))):
                    occurrence_ids.append([
                        insert(
                            "word_occurrences", "occurrence_id", word_id=word_id,
                            song_id=song_ids[index], stanza_id=stanza_ids[index], global_line_number=1,
                            line_number_in_stanza=1, position_in_line=position, position_in_song=position,
                            original_token="fixture",
                        )
                        for position, word_id in enumerate(word_ids, start=1)
                    ])
                group_id = insert("word_groups", "group_id", group_name=prefix, description="Deletion test")
                db_queries.query_insert_group_word(cursor, group_id, target_word)
                phrase_id = insert("phrases", "phrase_id", phrase_name=prefix, phrase_text="fixture")
                for song_id, ids in zip(song_ids, occurrence_ids):
                    db_queries.query_insert_phrase_occurrence(cursor, phrase_id, song_id, ids[0], ids[-1])

                fixture_service = SimpleNamespace(transaction=fixture_transaction)
                with patch.object(song_service, "get_database_service", return_value=fixture_service):
                    self.assertEqual(summary()[:3], (initial_summary[0] + 2,
                                                     initial_summary[1] + 3, initial_summary[2] + 2))
                    self.assertTrue(song_service.delete_song(song_ids[0]))
                    for table in ("songs", "stanzas", "word_occurrences", "phrase_occurrences"):
                        self.assertEqual(count(table, "song_id", song_ids[0]), 0, table)

                    # The other song and all of its dependent rows survive.
                    for table in ("songs", "stanzas", "word_occurrences", "phrase_occurrences"):
                        self.assertEqual(count(table, "song_id", song_ids[1]), 1, table)
                    for word_id in (shared_word, target_word, unused_word):
                        self.assertEqual(count("words", "word_id", word_id), 1)
                    self.assertEqual(count("word_groups", "group_id", group_id), 1)
                    self.assertEqual(count("group_words", "group_id", group_id), 1)
                    self.assertEqual(count("phrases", "phrase_id", phrase_id), 1)
                    self.assertEqual(summary()[:3], (initial_summary[0] + 1,
                                                     initial_summary[1] + 1, initial_summary[2] + 1))
                    self.assertFalse(song_service.delete_song(song_ids[0]))

                    self.assertTrue(song_service.delete_song(song_ids[1]))
                    self.assertEqual(summary(), initial_summary)
                    self.assertEqual(count("phrases", "phrase_id", phrase_id), 1)
                    self.assertEqual(count("phrase_occurrences", "phrase_id", phrase_id), 0)
                    self.assertEqual(count("group_words", "group_id", group_id), 1)
                    for word_id in (shared_word, target_word, unused_word):
                        self.assertEqual(count("words", "word_id", word_id), 1)
            finally:
                cursor.connection.rollback()

            self.assertEqual(snapshot(), original, "All original database contents must remain unchanged")


if __name__ == "__main__":
    unittest.main()
