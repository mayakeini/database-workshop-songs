import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import MagicMock, patch

from src import db, group_service, search_service, song_service, xml_service


def make_connection():
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value
    cursor.__enter__.return_value = cursor
    return connection, cursor


class DatabaseServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection, self.cursor = make_connection()
        self.pool = MagicMock()
        self.pool.acquire.return_value = self.connection
        self.service = db.DatabaseService(self.pool)

    def assert_released(self):
        self.cursor.__exit__.assert_called_once()
        self.connection.__exit__.assert_called_once()

    def test_read_returns_results_and_releases_resources_without_commit(self):
        self.cursor.fetchall.return_value = [(1, "hello")]

        def read():
            with self.service.read_cursor() as cursor:
                return cursor.fetchall()

        self.assertEqual(read(), [(1, "hello")])
        self.connection.commit.assert_not_called()
        self.assert_released()

    def test_read_failure_propagates_and_releases_resources(self):
        error = RuntimeError("query failed")
        with self.assertRaises(RuntimeError) as raised:
            with self.service.read_cursor():
                raise error

        self.assertIs(raised.exception, error)
        self.connection.commit.assert_not_called()
        self.assert_released()

    def test_transaction_commits_once_after_the_entire_operation(self):
        with self.service.transaction() as cursor:
            cursor.execute("first write")
            self.connection.commit.assert_not_called()
            cursor.execute("second write")
            self.connection.commit.assert_not_called()

        self.connection.commit.assert_called_once_with()
        self.connection.rollback.assert_not_called()
        self.assert_released()

    def test_early_return_still_commits_and_releases_resources(self):
        def write():
            with self.service.transaction():
                return 42

        self.assertEqual(write(), 42)
        self.connection.commit.assert_called_once_with()
        self.assert_released()

    def test_transaction_rolls_back_errors_and_interruptions(self):
        for error in (ValueError("invalid data"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                self.connection.reset_mock()
                with self.assertRaises(type(error)) as raised:
                    with self.service.transaction():
                        raise error

                self.assertIs(raised.exception, error)
                self.connection.commit.assert_not_called()
                self.connection.rollback.assert_called_once_with()
                self.assert_released()

    def test_commit_failure_rolls_back_and_propagates(self):
        error = RuntimeError("commit failed")
        self.connection.commit.side_effect = error
        with self.assertRaises(RuntimeError) as raised:
            with self.service.transaction():
                pass

        self.assertIs(raised.exception, error)
        self.connection.rollback.assert_called_once_with()
        self.assert_released()

    def test_rollback_failure_preserves_original_error(self):
        error = ValueError("invalid data")
        self.connection.rollback.side_effect = RuntimeError("connection lost")
        with self.assertLogs("src.db", level="ERROR"):
            with self.assertRaises(ValueError) as raised:
                with self.service.transaction():
                    raise error

        self.assertIs(raised.exception, error)
        self.assert_released()

    def test_cursor_creation_failure_releases_connection(self):
        for method in (self.service.read_cursor, self.service.transaction):
            with self.subTest(method=method.__name__):
                self.connection.reset_mock()
                self.connection.cursor.side_effect = RuntimeError("cursor failed")
                with self.assertRaisesRegex(RuntimeError, "cursor failed"):
                    with method():
                        self.fail("A cursor must not be yielded")

                self.connection.commit.assert_not_called()
                self.connection.__exit__.assert_called_once()

    def test_cursor_close_failure_prevents_commit_and_releases_connection(self):
        self.cursor.__exit__.side_effect = RuntimeError("cursor close failed")
        with self.assertRaisesRegex(RuntimeError, "cursor close failed"):
            with self.service.transaction():
                pass

        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once_with()
        self.connection.__exit__.assert_called_once()

    def test_acquisition_failure_does_not_yield_a_cursor(self):
        self.pool.acquire.side_effect = RuntimeError("pool exhausted")
        for method in (self.service.read_cursor, self.service.transaction):
            with self.subTest(method=method.__name__):
                with self.assertRaisesRegex(RuntimeError, "pool exhausted"):
                    with method():
                        self.fail("A cursor must not be yielded")

        self.connection.cursor.assert_not_called()

    def test_concurrent_operations_have_independent_transactions(self):
        barrier = Barrier(2)
        connections = []

        def acquire():
            connection, cursor = make_connection()
            connections.append((connection, cursor))
            return connection

        self.pool.acquire.side_effect = acquire

        def write(fail):
            with self.service.transaction() as cursor:
                cursor.execute("write", fail=fail)
                barrier.wait(timeout=5)
                if fail:
                    raise ValueError("one operation failed")

        with ThreadPoolExecutor(max_workers=2) as executor:
            success = executor.submit(write, False)
            failure = executor.submit(write, True)
            success.result(timeout=10)
            with self.assertRaisesRegex(ValueError, "one operation failed"):
                failure.result(timeout=10)

        self.assertEqual(len(connections), 2)
        self.assertIsNot(connections[0][1], connections[1][1])
        for connection, cursor in connections:
            if cursor.execute.call_args.kwargs["fail"]:
                connection.commit.assert_not_called()
                connection.rollback.assert_called_once_with()
            else:
                connection.commit.assert_called_once_with()
                connection.rollback.assert_not_called()
            cursor.__exit__.assert_called_once()
            connection.__exit__.assert_called_once()

    def test_session_timezone_is_initialized_and_cursor_closed(self):
        db._initialize_session(self.connection, None)
        self.cursor.execute.assert_called_once_with(
            "ALTER SESSION SET TIME_ZONE = '+03:00'"
        )
        self.cursor.__exit__.assert_called_once()

    def test_session_initialization_failure_closes_cursor_and_propagates(self):
        self.cursor.execute.side_effect = RuntimeError("session setup failed")
        with self.assertRaisesRegex(RuntimeError, "session setup failed"):
            db._initialize_session(self.connection, None)
        self.cursor.__exit__.assert_called_once()

    def test_close_releases_pool(self):
        self.service.close()
        self.pool.close.assert_called_once_with()


class DatabaseFactoryTests(unittest.TestCase):
    def setUp(self):
        db.get_database_service.clear()
        self.addCleanup(db.get_database_service.clear)

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.db.oracledb.create_pool")
    def test_service_is_cached_and_uses_local_defaults(self, create_pool):
        first = db.get_database_service()
        self.assertIs(db.get_database_service(), first)
        create_pool.assert_called_once()
        settings = create_pool.call_args.kwargs
        self.assertEqual(settings["dsn"], "localhost:1521/FREEPDB1")
        self.assertEqual(settings["user"], "concordance")
        self.assertEqual(settings["password"], "songsproject")
        self.assertIs(settings["session_callback"], db._initialize_session)

    @patch.dict(os.environ, {
        "ORACLE_HOST": "db.example",
        "ORACLE_PORT": "1522",
        "ORACLE_SERVICE": "TESTPDB",
        "ORACLE_USER": "test_user",
        "ORACLE_PASSWORD": "test_password",
    })
    @patch("src.db.oracledb.create_pool")
    def test_environment_overrides_connection_settings(self, create_pool):
        db.get_database_service()
        settings = create_pool.call_args.kwargs
        self.assertEqual(settings["dsn"], "db.example:1522/TESTPDB")
        self.assertEqual(settings["user"], "test_user")
        self.assertEqual(settings["password"], "test_password")

    @patch("src.db.oracledb.create_pool")
    def test_failed_creation_can_be_retried(self, create_pool):
        create_pool.side_effect = [RuntimeError("database unavailable"), MagicMock()]
        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            db.get_database_service()
        service = db.get_database_service()
        self.assertIs(db.get_database_service(), service)
        self.assertEqual(create_pool.call_count, 2)


class BusinessTransactionTests(unittest.TestCase):
    def setUp(self):
        self.connection, self.cursor = make_connection()
        self.cursor.var.return_value.getvalue.return_value = [123]
        self.pool = MagicMock()
        self.pool.acquire.return_value = self.connection
        service = db.DatabaseService(self.pool)
        for module in (group_service, search_service, song_service, xml_service):
            patcher = patch.object(module, "get_database_service", return_value=service)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_search_returns_existing_results_without_commit(self):
        rows = [(1, "Song", 2, 3)]
        self.cursor.fetchall.return_value = rows
        self.assertEqual(search_service.search_word("hello"), rows)
        self.connection.commit.assert_not_called()
        self.connection.__exit__.assert_called_once()

    def test_duplicate_group_rolls_back_and_keeps_validation_error(self):
        self.cursor.fetchone.return_value = (123,)
        with self.assertLogs("src.group_service", level="WARNING"):
            with self.assertRaisesRegex(ValueError, "already exists"):
                group_service.create_group("Existing group")
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once_with()

    def insert_song(self):
        occurrence = {
            "normalized_word": "hello",
            "original_token": "Hello",
            "stanza_number": 1,
            "global_line_number": 1,
            "line_number_in_stanza": 1,
            "position_in_line": 1,
            "position_in_song": 1,
        }
        self.cursor.fetchone.return_value = None
        with patch.object(song_service, "song_exists", return_value=False):
            with patch.object(song_service, "parse_song", return_value=[occurrence]):
                return song_service.insert_song("song.txt", "Song", "Artist", None, 2020)

    def test_song_upload_commits_all_inserts_together(self):
        self.assertEqual(self.insert_song(), 123)
        statements = [call.args[0] for call in self.cursor.execute.call_args_list]
        for table in ("songs", "stanzas", "words", "word_occurrences"):
            self.assertTrue(any(f"INSERT INTO {table} (" in sql for sql in statements))
        self.pool.acquire.assert_called_once_with()
        self.connection.commit.assert_called_once_with()
        self.connection.rollback.assert_not_called()

    def test_song_upload_failure_after_inserts_rolls_back_everything(self):
        def execute(sql, **parameters):
            self.connection.commit.assert_not_called()
            if "INSERT INTO word_occurrences" in sql:
                raise RuntimeError("occurrence insert failed")

        self.cursor.execute.side_effect = execute
        with self.assertLogs("src.song_service", level="ERROR"):
            with self.assertRaisesRegex(RuntimeError, "occurrence insert failed"):
                self.insert_song()
        self.pool.acquire.assert_called_once_with()
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once_with()
        self.connection.__exit__.assert_called_once()

    def restore_xml(self, stanza_song_id=1):
        return f"""<concordance_backup>
            <songs><song id="1">
                <title>Song</title><artist>Artist</artist>
                <publication_year>2020</publication_year>
                <upload_date>2020-01-01T12:00:00</upload_date>
            </song></songs>
            <stanzas><stanza id="1">
                <song_id>{stanza_song_id}</song_id><stanza_number>1</stanza_number>
            </stanza></stanzas>
            <words/><word_occurrences/><word_groups/><group_words/>
            <phrases/><phrase_occurrences/>
        </concordance_backup>""".encode()

    def test_xml_restore_commits_deletions_and_inserts_once(self):
        counts = xml_service.restore_database_from_xml(self.restore_xml())
        self.assertEqual(counts["songs"], 1)
        self.assertEqual(counts["stanzas"], 1)
        statements = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertEqual(sum("DELETE FROM" in sql for sql in statements), 8)
        self.assertTrue(any("INSERT INTO songs" in sql for sql in statements))
        self.pool.acquire.assert_called_once_with()
        self.connection.commit.assert_called_once_with()
        self.connection.rollback.assert_not_called()

    def test_invalid_xml_reference_rolls_back_deletions_and_prior_inserts(self):
        with self.assertLogs("src.xml_service", level="ERROR"):
            with self.assertRaises(KeyError):
                xml_service.restore_database_from_xml(self.restore_xml(stanza_song_id=999))
        statements = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertEqual(sum("DELETE FROM" in sql for sql in statements), 8)
        self.assertTrue(any("INSERT INTO songs" in sql for sql in statements))
        self.pool.acquire.assert_called_once_with()
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once_with()
        self.connection.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
