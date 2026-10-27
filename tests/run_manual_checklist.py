"""Execute BB01–BB26 and WB01–WB15 against actual Oracle and Streamlit pages.

Run from the repository root (the dedicated Oracle container must be running):
  RUN_MANUAL_CHECKLIST=1 ORACLE_PORT=1522 PYTHONDONTWRITEBYTECODE=1 \
    .venv/bin/python -m tests.run_manual_checklist

WARNING: Replaces data on localhost:1522 and stops/restarts only the dedicated
container named in checklist_support.CONTAINER. Never targets port 1521.
The original nine sample files are explicitly listed; tester.txt is excluded.
Set SINGLE_USER_TESTS=1 to skip concurrent-operation scenarios.
"""
from collections import Counter
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import importlib.util
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier
import time
import traceback
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import oracledb
from streamlit.testing.v1 import AppTest
from src import db, group_service as groups, phrase_service as phrases
from src import search_service as search, song_service as songs
from src import statistics_service as stats, xml_service as xml
from src.text_parser import parse_song
from tests.checklist_support import *


class Checklist(unittest.TestCase):
    baseline = None
    observations = {}

    @classmethod
    def setUpClass(cls):
        setup_database()

    def setUp(self):
        if type(self).baseline is not None:
            xml.restore_database_from_xml(type(self).baseline)

    def note(self, **details):
        self.observations.setdefault(self._testMethodName, {}).update(details)

    def assert_ui_ok(self, at):
        self.assertEqual(texts(at.error), "")

    def test_BB01_empty_pages(self):
        for path in PAGES:
            with self.subTest(page=path):
                at = page(path)
                errors = [e.value for e in at.error if "Restoring a backup replaces" not in e.value]
                self.assertEqual(errors, [])
        at = page("pages/2_search.py")
        click(at, "Search Songs")
        self.assertIn("No songs found", texts(at.info))
        at.text_input(key="search_word").set_value("love")
        click(at, "Search Word")
        self.assertIn("not found", texts(at.info))
        self.assertEqual(counts()["songs"], 0)

    def test_BB02_staged_upload_phrase_refresh(self):
        at = upload(0)
        self.assert_ui_ok(at)
        self.assertEqual(metrics(at), {"Stanzas": "2", "Lines": "4", "Words": "16"})
        at = create_phrase_ui("Love phrase", "love is")
        self.assert_ui_ok(at)
        pid = phrases.get_phrases()[0][0]
        self.assertEqual(len(phrases.get_phrase_occurrences(pid)), 2)
        self.assert_ui_ok(upload(1))
        self.assertEqual(len(phrases.get_phrase_occurrences(pid)), 3)

    def test_BB03_all_sample_uploads(self):
        # Recover setup after a prior assertion failure, without hiding that failure.
        for index, (filename, title, artist, stanzas, lines, words, unique) in enumerate(FILES):
            if not songs.song_exists(title, artist, None):
                self.assert_ui_ok(upload(index))
            sid = song_id(title)
            self.assertEqual(songs.get_uploaded_song_summary(sid),
                             {"stanzas": stanzas, "lines": lines, "words": words})
            self.assertEqual(stats.get_song_statistics(sid)["unique_word_count"], unique)
        if not phrases.get_phrases():
            phrases.create_and_search_phrase("Love phrase", "love is")
        self.assertEqual(counts()["songs"], 9)
        self.assertEqual(len(page("pages/8_all_songs.py").dataframe[0].value), 9)
        type(self).baseline = xml.export_database_to_xml()
        (TESTS / "checklist_baseline.xml").write_bytes(type(self).baseline)
        self.note(counts=counts(), statistics=stats.get_database_summary())

    def test_BB04_required_upload_fields(self):
        before = counts()
        for title, artist, message in [("", "Test", "title"), ("   ", "Test", "title"),
                                        ("New", "", "Artist")]:
            with self.subTest(title=title, artist=artist):
                at = upload(title=title, artist=artist)
                self.assertIn(message.lower(), texts(at.error).lower())
        at = page("pages/1_upload_song.py")
        at.text_input(key="song_title").set_value("New")
        at.text_input(key="song_artist").set_value("Test")
        click(at, "Upload Song")
        self.assertIn("upload a TXT", texts(at.error))
        self.assertEqual(counts(), before)

    def test_BB05_year_boundaries(self):
        current = datetime.now().year
        at = page("pages/1_upload_song.py")
        self.assertEqual(at.number_input[0].min, 1000)
        self.assertEqual(at.number_input[0].max, current)
        for year in (1000, current):
            self.assert_ui_ok(upload(title=f"Year {year}", year=year))
        for year in (999, current + 1):
            with self.assertRaises(ValueError):
                songs.insert_song(str(SAMPLES / FILES[0][0]), f"Year {year}", "Test", None, year)
        self.assertEqual(counts()["songs"], 11)

    def test_BB06_duplicate_songs(self):
        before = raw_snapshot()
        for title, artist, year in [("Example", "Test Artist", 2000),
                                    (" example ", " TEST ARTIST ", 2000),
                                    ("Example", "Test Artist", 2001)]:
            at = upload(title=title, artist=artist, year=year)
            self.assertIn("already exists", texts(at.error))
        self.assertEqual(raw_snapshot(), before)

    def test_BB07_upload_reset(self):
        at = upload(title="Reset check")
        self.assert_ui_ok(at)
        self.assertTrue(button(at, "Upload Song").disabled)
        self.assertTrue(all(x.disabled for x in at.text_input))
        self.assertTrue(at.file_uploader[0].disabled)
        click(at, "Upload Another Song")
        self.assertFalse(button(at, "Upload Song").disabled)
        self.assertEqual(at.text_input(key="song_title").value, "")
        self.assertIsNone(at.file_uploader[0].value)
        self.assertEqual(counts()["songs"], 10)

    def test_BB08_text_reconstruction(self):
        expected = (SAMPLES / "example.txt").read_text().strip()
        self.assertEqual(songs.get_song_text(song_id()), expected)
        at = page("pages/8_all_songs.py")
        at.selectbox[0].set_value(song_id())
        run(at)
        self.assertIn(expected, texts(at.text))
        at = page("pages/2_search.py")
        at.text_input(key="search_song_title").set_value("Example")
        click(at, "Search Songs")
        self.assertIn(expected, texts(at.text))

    def test_BB09_metadata_filters(self):
        for title, artist, expected in [("halle", "", "Hallelujah"), ("", "QUEEN", "Don’t Stop Me Now"),
                                         ("heart", "Celine", "My Heart Will Go On")]:
            at = page("pages/2_search.py")
            at.text_input(key="search_song_title").set_value(title)
            at.text_input(key="search_song_artist").set_value(artist)
            click(at, "Search Songs")
            self.assertEqual(len(at.expander), 1)
            self.assertIn(expected, at.expander[0].label)
        at = page("pages/2_search.py")
        at.checkbox(key="search_use_year").check()
        run(at)
        at.number_input(key="search_publication_year").set_value(2000)
        click(at, "Search Songs")
        self.assertEqual(len(at.expander), 9)
        at.number_input(key="search_publication_year").set_value(1999)
        click(at, "Search Songs")
        self.assertIn("No songs found", texts(at.info))
        self.assertEqual(search.search_songs(title="' OR 1=1 --"), [])

    def test_BB10_word_search(self):
        at = page("pages/2_search.py")
        for word in ("love", "LOVE", " love "):
            at.text_input(key="search_word").set_value(word)
            click(at, "Search Word")
            self.assertEqual(len(at.session_state["word_search_results"]), 25)
        at.text_input(key="search_word").set_value("zzzznotaword")
        click(at, "Search Word")
        self.assertIn("not found", texts(at.info))

    def test_BB11_occurrence_navigation(self):
        at = page("pages/2_search.py")
        at.text_input(key="search_word").set_value("hallelujah")
        click(at, "Search Word")
        self.assertEqual(len(at.session_state["word_search_results"]), 39)
        self.assertTrue(at.button(key="word_occurrence_previous").disabled)
        for index in range(1, 39):
            at.button(key="word_occurrence_next").click()
            run(at)
            self.assertEqual(at.session_state["word_occurrence_index"], index)
            self.assertIn(f"Occurrence {index + 1} of 39", texts(at.caption))
        self.assertTrue(at.button(key="word_occurrence_next").disabled)
        for index in range(37, -1, -1):
            at.button(key="word_occurrence_previous").click()
            run(at)
            self.assertEqual(at.session_state["word_occurrence_index"], index)
        at.text_input(key="search_word").set_value("love")
        click(at, "Search Word")
        self.assertEqual(at.session_state["word_occurrence_index"], 0)
        at.text_input(key="search_word").set_value("")
        click(at, "Search Word")
        self.assertIsNone(at.session_state["word_search_results"])
        self.assertIn("enter a word", texts(at.error))

    def test_BB12_location_search(self):
        at = page("pages/2_search.py")
        selector = at.selectbox(key="location_song")
        selector.select(next(x for x in selector.options if x.startswith("Example —")))
        run(at)
        expected = songs.get_line(song_id(), 3)
        for mode in ("Global Line Number", "Stanza and Line", "Word Position"):
            at.radio(key="location_search_mode").set_value(mode)
            run(at)
            for field in at.number_input:
                if field.label == "Global Line Number": field.set_value(3)
                if field.label == "Stanza Number": field.set_value(2)
                if field.label == "Line Number in Stanza": field.set_value(1)
                if field.label == "Position in Line": field.set_value(5)
            click(at, "Find Location")
            if mode == "Word Position":
                self.assertIn("**Word:** air", texts(at.markdown))
                self.assertTrue(any(x.value.endswith(":** air,") for x in at.markdown))
                self.note(word_position_display=texts(at.markdown))
            else:
                self.assertIn(expected, texts(at.text))

    def test_BB13_invalid_location_context(self):
        sid = song_id()
        self.assertIsNone(search.find_line_by_global_number(sid, 9999))
        self.assertIsNone(search.find_line_by_stanza_position(sid, 99, 1))
        self.assertIsNone(search.find_word_by_position(sid, 1, 999))
        self.assertEqual(set(search.get_context(sid, 1)), {1, 2})
        self.assertEqual(set(search.get_context(sid, 4)), {3, 4})
        at = page("pages/2_search.py")
        for mode in ("Global Line Number", "Stanza and Line", "Word Position"):
            at.radio(key="location_search_mode").set_value(mode)
            run(at)
            for field in at.number_input:
                if field.key != "search_publication_year":
                    self.assertEqual(field.min, 1)
                    field.set_value(9999)
            click(at, "Find Location")
            self.assertIn("No text was found", texts(at.info))

    def test_BB14_index_csv(self):
        at = page("pages/3_word_index.py")
        for fragment, expected in [("All Songs", 2379), ("Example —", 16), ("Don’t Stop Me Now —", 367)]:
            selector = at.selectbox[0]
            selector.select(next(x for x in selector.options if x.startswith(fragment)))
            run(at)
            data = at.dataframe[0].value
            self.assertEqual(len(data), expected)
            self.assertEqual(data["Word"].tolist(), sorted(data["Word"].tolist()))
            csv_rows = csv_rows_from_button(at)
            self.assertEqual(len(csv_rows), expected)
            self.assertEqual(list(csv_rows[0]), list(data.columns))
            self.assertEqual(csv_rows, [{k: str(v) for k, v in row.items()} for row in data.to_dict("records")])
            self.assertFalse(at.download_button[0].disabled)

    def test_BB15_group_index_filters(self):
        at = create_group_ui()
        self.assert_ui_ok(at)
        gid = groups.get_groups()[0][0]
        at.text_input(key=f"word_to_add_{gid}_0").set_value("hallelujah")
        click(at, "Add Word")
        self.assert_ui_ok(at)
        self.assertEqual(len(groups.get_group_words(gid)), 2)
        self.assertEqual(len(groups.get_group_occurrences(gid)), 64)
        at = page("pages/3_word_index.py")
        at.selectbox(key="index_group_filter").select("Selected Words")
        run(at)
        self.assertEqual(len(at.dataframe[0].value), 64)
        at.selectbox[0].select(next(x for x in at.selectbox[0].options if x.startswith("Hallelujah —")))
        run(at)
        self.assertEqual(len(at.dataframe[0].value), 40)

    def test_BB16_group_validation(self):
        for name, first, error in [("", "love", "name"), ("Empty", "", "at least one"),
                                    ("Unknown", "zzzznotaword", "does not exist")]:
            at = create_group_ui(name, first)
            self.assertIn(error, texts(at.error))
        at = create_group_ui()
        gid = groups.get_groups()[0][0]
        at.text_input(key=f"word_to_add_{gid}_0").set_value("LOVE")
        click(at, "Add Word")
        self.assertIn("already in", texts(at.error))
        at = create_group_ui("selected WORDS", "love")
        self.assertIn("already exists", texts(at.error))
        self.assertEqual(len(groups.get_groups()), 1)
        self.assertEqual(len(groups.get_group_words(gid)), 1)

    def test_BB17_group_edit_remove_delete(self):
        gid = groups.create_group("Selected Words", first_word="love")
        groups.add_word_to_group(gid, "hallelujah")
        before = counts()
        at = page("pages/4_word_groups.py")
        at.text_input(key=f"edit_group_name_{gid}").set_value("Renamed")
        at.text_area(key=f"edit_group_description_{gid}").set_value("Checklist description")
        click(at, "Save Changes")
        self.assertEqual(groups.get_groups()[0][1:3], ("Renamed", "Checklist description"))
        at.selectbox(key=f"remove_word_select_{gid}").select("hallelujah")
        click(at, "Remove Word")
        self.assertEqual(len(groups.get_group_words(gid)), 1)
        click(at, "Remove Word")
        self.assertIn("at least one word", texts(at.error))
        self.assertTrue(at.button(key=f"delete_group_{gid}").disabled)
        at.checkbox(key=f"confirm_delete_group_{gid}").check()
        run(at)
        at.button(key=f"delete_group_{gid}").click()
        run(at)
        self.assertEqual(groups.get_groups(), [])
        self.assertEqual(counts()["words"], before["words"])
        self.assertEqual(counts()["word_occurrences"], before["word_occurrences"])

    def test_BB18_phrase_counts(self):
        for text, expected, song in [("let it be", 41, "Let It Be"),
                                      ("always love you", 11, "I Will Always Love You"),
                                      ("lover to lover", 15, "Lover To Lover")]:
            at = create_phrase_ui(text, text)
            self.assert_ui_ok(at)
            pid = next(p[0] for p in phrases.get_phrases() if p[1] == text)
            results = phrases.get_phrase_occurrences_with_context(pid)
            self.assertEqual(len(results), expected)
            self.assertEqual({x["song_title"] for x in results}, {song})
            self.assertTrue(all(x["global_line_number"] in x["context"] for x in results))

    def test_BB19_phrase_overlap_boundaries(self):
        self.assert_ui_ok(create_phrase_ui("Overlap", "go go"))
        pid = next(p[0] for p in phrases.get_phrases() if p[1] == "Overlap")
        results = phrases.get_phrase_occurrences(pid)
        self.assertEqual([(r[2], r[3], r[4]) for r in results], [(12, 3, 4), (12, 4, 5)])
        self.assert_ui_ok(create_phrase_ui("Cross line", "trouble mother"))
        pid = next(p[0] for p in phrases.get_phrases() if p[1] == "Cross line")
        self.assertEqual(phrases.get_phrase_occurrences(pid), [])

    def test_BB20_phrase_validation_delete(self):
        self.assert_ui_ok(create_phrase_ui("Normalized", "LOVE, IS!"))
        pid = next(p[0] for p in phrases.get_phrases() if p[1] == "Normalized")
        self.assertEqual(len(phrases.get_phrase_occurrences(pid)), 3)
        for name, text, error in [("", "love", "name"), ("Blank", "", "text"),
                                   ("Punctuation", "!!! ...", "valid words"),
                                   ("Normalized", "love", "already exists")]:
            at = create_phrase_ui(name, text)
            self.assertIn(error, texts(at.error).lower())
        before = counts()
        at = page("pages/5_phrases.py")
        at.selectbox[0].select(next(x for x in at.selectbox[0].options if x.startswith("Normalized")))
        run(at)
        self.assertTrue(button(at, "Delete Phrase").disabled)
        at.checkbox(key=f"confirm_delete_phrase_{pid}").check()
        run(at)
        click(at, "Delete Phrase")
        self.assertNotIn(pid, [p[0] for p in phrases.get_phrases()])
        self.assertEqual(counts()["songs"], before["songs"])
        self.assertEqual(counts()["words"], before["words"])

    def test_BB21_statistics(self):
        self.assertEqual(stats.get_database_summary(), {
            "song_count": 9, "total_words": 2379, "unique_words": 454,
            "average_word_length": 3.91, "average_words_per_line": 6.33})
        self.assertEqual(stats.get_words_per_stanza(song_id()), [(1, 7), (2, 9)])
        self.assertEqual(stats.get_song_statistics(song_id())["average_word_length"], 4.0)
        self.assertEqual(stats.get_most_frequent_words(1), [("you", 114)])
        at = page("pages/6_statistics.py")
        self.assert_ui_ok(at)
        self.assertIn("2,379", " ".join(metrics(at).values()).replace("2379", "2,379"))
        selector = at.selectbox[0]
        selector.select(next(x for x in selector.options if x.startswith("Example —")))
        run(at)
        self.assert_ui_ok(at)
        self.assertEqual(len(at._checklist_charts), 3)
        chart_data = []
        for chart in at._checklist_charts:
            self.assertTrue(chart["encoding"]["tooltip"])
            chart_data.append(next(iter(chart["datasets"].values())))
        self.assertIn({"Word": "is", "Occurrences": 3}, chart_data[0])
        self.assertEqual(sum(x["Occurrences"] for x in chart_data[1]), 16)
        self.assertEqual(chart_data[2], [{"Stanza": 1, "Word Count": 7}, {"Stanza": 2, "Word Count": 9}])
        self.note(database_statistics=stats.get_database_summary(), example_metrics=metrics(at),
                  chart_count=len(at._checklist_charts), chart_data=chart_data)

    def test_BB22_xml_round_trip(self):
        gid = groups.create_group("Backup Group", first_word="love")
        groups.add_word_to_group(gid, "hallelujah")
        original = semantic_snapshot()
        at = page("pages/7_backup_restore.py")
        self.assertTrue(button(at, "Restore Database").disabled)
        click(at, "Generate XML Backup")
        backup = at.session_state["xml_backup_data"]
        self.assertTrue(backup.startswith(b"<?xml"))
        self.assertEqual(len(at.download_button), 1)
        self.assert_ui_ok(upload(title="Extra copy"))
        at = restore_ui(backup, confirm=False)
        self.assertTrue(button(at, "Restore Database").disabled)
        at.checkbox(key="confirm_xml_restore").check()
        run(at)
        click(at, "Restore Database")
        self.assertIn("restored successfully", texts(at.success))
        self.assertEqual(semantic_snapshot(), original)
        self.assertEqual(counts()["songs"], 9)

    def test_BB23_invalid_backups(self):
        before = raw_snapshot()
        root = ET.fromstring(type(self).baseline)
        root.remove(root.find("words"))
        for data in (b"<broken", b"<wrong/>", ET.tostring(root)):
            at = restore_ui(data)
            errors = [x.value for x in at.error if "Restoring a backup replaces" not in x.value]
            self.assertTrue(errors)
            self.assertEqual(raw_snapshot(), before)

    def test_BB24_search_state_after_restore(self):
        # Same real Streamlit session navigates between Search and Restore.
        at = page("app.py")
        at.switch_page("pages/2_search.py")
        run(at)
        at.text_input(key="search_word").set_value("love")
        click(at, "Search Word")
        old_ids = [r[1] for r in at.session_state["word_search_results"]]
        at.switch_page("pages/7_backup_restore.py")
        run(at)
        # A smaller backup guarantees the cached collection is now different.
        songs.delete_song(song_id("I Will Always Love You"))
        smaller = xml.export_database_to_xml()
        at.file_uploader[0].set_value(("smaller.xml", smaller, "application/xml"))
        at.checkbox(key="confirm_xml_restore").check()
        run(at)
        click(at, "Restore Database")
        at.switch_page("pages/2_search.py")
        run(at)
        cached = at.session_state["word_search_results"]
        live = search.search_word("love")
        self.note(cached_count=len(cached) if cached else 0, live_count=len(live),
                  cached_song_ids=sorted(set(old_ids)), live_song_ids=sorted({r[1] for r in live}))
        self.assertTrue(cached is None or cached == live,
                        f"Stale search after restore: {len(cached or [])} cached vs {len(live)} live occurrences")
        self.assertEqual(at.session_state["word_occurrence_index"], 0)
        self.assertIsNone(at.session_state["word_search_error"])
        at.text_input(key="search_word").set_value("love")
        click(at, "Search Word")
        self.assertEqual(at.session_state["word_search_results"], live)

    def test_BB25_database_outage(self):
        # Stop only our isolated database; original user's container is untouched.
        baseline = raw_snapshot()
        subprocess.run(["docker", "stop", "-t", "10", CONTAINER], check=True, capture_output=True)
        try:
            db.get_database_service().oracle_con_pool.close(force=True)
            db.get_database_service.clear()
            for path in ("app.py", "pages/2_search.py", "pages/3_word_index.py", "pages/4_word_groups.py",
                         "pages/5_phrases.py", "pages/6_statistics.py", "pages/8_all_songs.py"):
                at = page(path)
                self.assertTrue(len(at.error), path)
            at = upload(title="Outage upload")
            self.assertIn("Could not upload", texts(at.error))
            self.assertFalse(len(at.success))
        finally:
            subprocess.run(["docker", "start", CONTAINER], check=True, capture_output=True)
            deadline = time.monotonic() + 120
            while True:
                try:
                    with oracledb.connect(user="concordance", password="songsproject", dsn="localhost:1522/FREEPDB1"):
                        break
                except oracledb.Error:
                    if time.monotonic() > deadline: raise
                    time.sleep(1)
            db.get_database_service.clear()
        self.assertEqual(raw_snapshot(), baseline)
        self.assert_ui_ok(page("app.py"))
        self.assert_ui_ok(upload(title="Recovery upload"))

    def test_BB26_same_name_different_albums(self):
        self.assert_ui_ok(upload(album="Other Album"))
        results = {}
        for path in ("pages/3_word_index.py", "pages/6_statistics.py", "pages/8_all_songs.py"):
            at = page(path)
            results[path] = [x for x in at.selectbox[0].options if x.startswith("Example —")]
        self.note(selector_options=results)
        self.assertTrue(all(len(x) == 2 for x in results.values()),
                        f"Both albums must be selectable; options found: {results}")

    def test_WB01_parser_positions(self):
        rows = parse_song(str(SAMPLES / "example.txt"))
        self.assertEqual(len(rows), 16)
        self.assertEqual([r["position_in_song"] for r in rows], list(range(1, 17)))
        self.assertEqual([(r["global_line_number"], r["position_in_line"], r["position_in_song"])
                          for r in rows if r["normalized_word"] == "love"], [(3, 1, 8), (4, 2, 14)])

    def test_WB02_stanza_transition(self):
        rows = parse_song(str(SAMPLES / "example.txt"))
        self.assertEqual((rows[6]["global_line_number"], rows[6]["stanza_number"], rows[6]["line_number_in_stanza"]), (2, 1, 2))
        self.assertEqual((rows[7]["global_line_number"], rows[7]["stanza_number"], rows[7]["line_number_in_stanza"]), (3, 2, 1))
        self.assertEqual(len({r["global_line_number"] for r in rows}), 4)

    def test_WB03_standalone_punctuation(self):
        rows = [r for r in parse_song(str(SAMPLES / FILES[7][0])) if r["global_line_number"] == 9]
        self.assertEqual(len(rows), 10)
        self.assertEqual((rows[5]["normalized_word"], rows[5]["original_token"], rows[5]["position_in_line"]), ("face", "face&", 6))
        self.assertEqual((rows[6]["normalized_word"], rows[6]["position_in_line"]), ("that", 7))

    def test_WB04_apostrophes(self):
        rows = parse_song(str(SAMPLES / FILES[2][0]))
        self.assertEqual(sum(r["normalized_word"] == "don't" for r in rows), 21)
        self.assertTrue(any(r["normalized_word"] == "i'm" and r["original_token"] == "I'm" for r in rows))
        self.assertTrue(all(r["normalized_word"] == r["normalized_word"].lower() for r in rows))

    def test_WB05_vocabulary_reuse(self):
        self.assertEqual(counts()["words"], 454)
        self.assertEqual(counts()["word_occurrences"], 2379)
        self.assertEqual(query("SELECT COUNT(*), COUNT(DISTINCT wo.word_id) FROM word_occurrences wo JOIN words w ON wo.word_id=w.word_id WHERE w.text='love'"), [(25, 1)])

    def test_WB06_both_phrase_matching_paths(self):
        # Definitions exist before their matching song is reuploaded.
        songs.delete_song(song_id("Don’t Stop Me Now"))
        songs.delete_song(song_id("Let It Be"))
        overlap = phrases.create_and_search_phrase("Overlap refresh", "go go")
        boundary = phrases.create_and_search_phrase("Boundary refresh", "trouble mother")
        self.assertEqual(phrases.get_phrase_occurrences(overlap), [])
        self.assert_ui_ok(upload(2))
        self.assert_ui_ok(upload(4))
        refreshed = phrases.get_phrase_occurrences(overlap)
        self.assertEqual([(r[2], r[3], r[4]) for r in refreshed], [(12, 3, 4), (12, 4, 5)])
        self.assertEqual(phrases.get_phrase_occurrences(boundary), [])
        created = phrases.create_and_search_phrase("Overlap create", "go go")
        self.assertEqual(phrases.get_phrase_occurrences(created), refreshed)

    def test_WB07_upload_atomicity(self):
        original = raw_snapshot()
        # Empty all tables inside the isolated schema to cover new vocabulary too.
        empty = b'<concordance_backup><songs/><stanzas/><words/><word_occurrences/><word_groups/><group_words/><phrases/><phrase_occurrences/></concordance_backup>'
        xml.restore_database_from_xml(empty)
        before = raw_snapshot()
        real_insert = songs.query_insert_word_occurrence
        calls = 0
        def failing_insert(*args, **kwargs):
            nonlocal calls
            calls += 1
            real_insert(*args, **kwargs)
            if calls == 8: raise RuntimeError("injected occurrence failure")
        with patch.object(songs, "query_insert_word_occurrence", side_effect=failing_insert):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                songs.insert_song(str(SAMPLES / FILES[8][0]), "Happy", "Pharrell Williams", None, 2000)
        self.assertEqual(calls, 8)
        self.assertEqual(raw_snapshot(), before)
        phrases.create_and_search_phrase("Refresh", "happy")
        before = raw_snapshot()
        real_phrase = phrases.query_insert_phrase_occurrence
        def failing_refresh(*args, **kwargs):
            real_phrase(*args, **kwargs)
            raise RuntimeError("injected refresh failure")
        with patch.object(phrases, "query_insert_phrase_occurrence", side_effect=failing_refresh):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                songs.insert_song(str(SAMPLES / FILES[8][0]), "Happy", "Pharrell Williams", None, 2000)
        self.assertEqual(raw_snapshot(), before)

    def test_WB08_group_phrase_atomicity(self):
        before = raw_snapshot()
        with patch.object(groups, "query_insert_group_word", side_effect=RuntimeError("injected membership failure")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                groups.create_group("Atomic group", first_word="love")
        self.assertEqual(raw_snapshot(), before)
        real = phrases.query_insert_phrase_occurrence
        def fail_after_insert(*args, **kwargs):
            real(*args, **kwargs)
            raise RuntimeError("injected phrase failure")
        with patch.object(phrases, "query_insert_phrase_occurrence", side_effect=fail_after_insert):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                phrases.create_and_search_phrase("Atomic phrase", "love is")
        self.assertEqual(raw_snapshot(), before)

    def test_WB09_transaction_branches(self):
        # Existing tests use controlled connection mocks for otherwise difficult
        # commit/rollback failure branches; real Oracle rollback also checked here.
        from tests.test_database_service import DatabaseServiceTests
        names = ["test_transaction_commits_once_after_the_entire_operation",
                 "test_transaction_rolls_back_errors_and_interruptions",
                 "test_commit_failure_rolls_back_and_propagates",
                 "test_rollback_failure_preserves_original_error",
                 "test_cursor_close_failure_prevents_commit_and_releases_connection"]
        result = unittest.TestResult()
        unittest.TestSuite(DatabaseServiceTests(name) for name in names).run(result)
        self.assertTrue(result.wasSuccessful(), str(result.errors + result.failures))
        before = raw_snapshot()
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with db.get_database_service().transaction() as cursor:
                cursor.execute("UPDATE songs SET album='uncommitted'")
                raise RuntimeError("rollback")
        self.assertEqual(raw_snapshot(), before)
        self.note(mock_failure_branch_checks=result.testsRun, real_oracle_rollback=True)

    def test_WB10_xml_mapping_rollback(self):
        gid = groups.create_group("Restore group", first_word="love")
        groups.add_word_to_group(gid, "hallelujah")
        backup = xml.export_database_to_xml()
        original = semantic_snapshot()
        old_ids = {r[0] for r in query("SELECT song_id FROM songs")}
        xml.restore_database_from_xml(backup)
        new_ids = {r[0] for r in query("SELECT song_id FROM songs")}
        self.assertTrue(old_ids.isdisjoint(new_ids))
        self.assertEqual(semantic_snapshot(), original)
        before = raw_snapshot()
        root = ET.fromstring(backup)
        root.find("phrase_occurrences/phrase_occurrence/end_occurrence_id").text = "999999999"
        with self.assertRaises(KeyError):
            xml.restore_database_from_xml(ET.tostring(root))
        self.assertEqual(raw_snapshot(), before)

    def test_WB11_constraints(self):
        gid = groups.create_group("Constraint Group", first_word="love")
        wid = groups.get_group_words(gid)[0][0]
        statements = [
            ("INSERT INTO words(text) VALUES ('love')", {}),
            ("INSERT INTO group_words(group_id,word_id) VALUES (:g,:w)", {"g":gid,"w":wid}),
            ("INSERT INTO word_groups(group_name) VALUES ('constraint GROUP')", {}),
            ("INSERT INTO group_words(group_id,word_id) VALUES (999999999,:w)", {"w":wid}),
            ("UPDATE word_occurrences SET position_in_line=0 WHERE occurrence_id=(SELECT MIN(occurrence_id) FROM word_occurrences)", {}),
            ("UPDATE word_occurrences SET position_in_song=1 WHERE song_id=:s AND position_in_song=2", {"s":song_id()}),
        ]
        before = raw_snapshot()
        codes = []
        for statement, parameters in statements:
            with self.assertRaises(oracledb.IntegrityError) as caught:
                with db.get_database_service().transaction() as cursor:
                    cursor.execute(statement, parameters)
            codes.append(caught.exception.args[0].code)
            self.assertEqual(raw_snapshot(), before)
        self.note(oracle_constraint_errors=codes)

    def test_WB12_cascades(self):
        gid = groups.create_group("Cascade group", first_word="love")
        pid = phrases.create_and_search_phrase("Cascade phrase", "love is")
        before = counts()
        groups.delete_group(gid)
        phrases.delete_phrase(pid)
        self.assertEqual(query("SELECT COUNT(*) FROM group_words WHERE group_id=:g", g=gid), [(0,)])
        self.assertEqual(query("SELECT COUNT(*) FROM phrase_occurrences WHERE phrase_id=:p", p=pid), [(0,)])
        self.assertEqual(counts()["words"], before["words"])
        snapshot = raw_snapshot()
        with db.get_database_service().read_cursor() as cursor:
            sid = song_id()
            cursor.execute("DELETE FROM songs WHERE song_id=:s", s=sid)
            for table in ("songs", "stanzas", "word_occurrences", "phrase_occurrences"):
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE song_id=:s", s=sid)
                self.assertEqual(cursor.fetchone()[0], 0)
            cursor.execute("SELECT COUNT(*) FROM words")
            self.assertEqual(cursor.fetchone()[0], before["words"])
            cursor.connection.rollback()
        self.assertEqual(raw_snapshot(), snapshot)

    def test_WB13_pool_limit(self):
        pool = db.get_database_service().oracle_con_pool
        held = [pool.acquire() for _ in range(4)]
        try:
            started = time.monotonic()
            with self.assertRaises(oracledb.Error):
                pool.acquire()
            elapsed = time.monotonic() - started
            self.assertGreaterEqual(elapsed, 4.5)
            self.assertLess(elapsed, 8)
            held.pop().close()
            with pool.acquire() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM dual")
                    self.assertEqual(cursor.fetchone(), (1,))
        finally:
            for connection in held: connection.close()
        self.note(pool_timeout_seconds=round(elapsed, 3))

    @unittest.skipIf(os.environ.get("SINGLE_USER_TESTS") == "1",
                     "Out of scope: one active user session with sequential operations")
    def test_WB14_concurrency_races(self):
        results = {}
        barrier = Barrier(2)
        real_exists = songs.song_exists
        def synchronized_exists(*args, **kwargs):
            result = real_exists(*args, **kwargs)
            barrier.wait(timeout=10)
            return result
        with patch.object(songs, "song_exists", side_effect=synchronized_exists):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(songs.insert_song, str(SAMPLES / "example.txt"),
                                           "Concurrent copy", "Test Artist", None, 2000) for _ in range(2)]
                outcomes = []
                for future in futures:
                    try: outcomes.append({"song_id": future.result(timeout=30)})
                    except Exception as error: outcomes.append({"error": str(error)})
        results["upload_outcomes"] = outcomes
        results["duplicate_song_count"] = query("SELECT COUNT(*) FROM songs WHERE title='Concurrent copy'")[0][0]
        gid = groups.create_group("Race group", first_word="love")
        groups.add_word_to_group(gid, "hallelujah")
        barrier = Barrier(2)
        real_delete = groups.query_delete_group_word_by_text
        def synchronized_delete(*args, **kwargs):
            # Both service calls have fetched and checked two members by here.
            barrier.wait(timeout=10)
            return real_delete(*args, **kwargs)
        with patch.object(groups, "query_delete_group_word_by_text", side_effect=synchronized_delete):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(groups.remove_word_from_group, gid, word) for word in ("love", "hallelujah")]
                results["remove_outcomes"] = [future.result(timeout=30) for future in futures]
        results["remaining_group_members"] = len(groups.get_group_words(gid))
        self.note(**results)
        self.assertTrue(results["duplicate_song_count"] == 1 and results["remaining_group_members"] >= 1,
                        f"Concurrency invariants violated: {results}")

    def test_WB15_temporary_cleanup(self):
        start = len(TEMP_PATHS)
        self.assert_ui_ok(upload(title="Temp success"))
        with patch.object(songs, "query_insert_word_occurrence", side_effect=RuntimeError("injected upload failure")):
            at = upload(title="Temp failure")
            self.assertIn("Could not upload", texts(at.error))
        created = TEMP_PATHS[start:]
        self.assertGreaterEqual(len(created), 2)
        self.assertTrue(all(not Path(path).exists() for path in created), created)
        self.note(temporary_files_created=len(created), all_removed=True)


class RecordingResult(unittest.TextTestResult):
    records = []
    def startTest(self, test):
        self.started = time.monotonic()
        super().startTest(test)
    def record(self, test, status, detail=""):
        self.records.append({"test": test._testMethodName, "status": status,
                             "seconds": round(time.monotonic() - self.started, 3), "detail": detail})
    def addSuccess(self, test):
        super().addSuccess(test); self.record(test, "PASS")
    def addFailure(self, test, err):
        super().addFailure(test, err); self.record(test, "FAIL", self._exc_info_to_string(err, test))
    def addError(self, test, err):
        super().addError(test, err); self.record(test, "ERROR", self._exc_info_to_string(err, test))
    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.record(test, "SKIP", reason)
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err: self.record(test, "FAIL", str(subtest) + "\n" + self._exc_info_to_string(err, test))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", help="Recheck selected IDs after the initial complete run")
    args = parser.parse_args()
    previous = None
    if args.only:
        if any(x in {"BB01", "BB02", "BB03"} for x in args.only):
            parser.error("Bootstrap cases must be run as part of the complete suite")
        Checklist.baseline = (TESTS / "checklist_baseline.xml").read_bytes()
        previous = json.loads((TESTS / "checklist_results.json").read_text())
    logging.basicConfig(filename=str(TESTS / "checklist_application.log"), level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Checklist)
    if args.only:
        suite = unittest.TestSuite(test for test in suite if test._testMethodName.split("_")[1] in args.only)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    report = {"executed_at": datetime.now().astimezone().isoformat(),
              "target": "localhost:1522/FREEPDB1 (disposable container)",
              "method": "Streamlit AppTest with real Oracle; explicit white-box fault/race injection",
              "single_user": os.environ.get("SINGLE_USER_TESTS") == "1",
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped),
              "results": result.records, "observations": Checklist.observations}
    if previous:
        (TESTS / "checklist_recheck_results.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
        replacements = {r["test"]: r for r in report["results"]}
        previous["results"] = [replacements.get(r["test"], r) for r in previous["results"]]
        previous["observations"].update(report["observations"])
        previous["failures"] = sum(r["status"] == "FAIL" for r in previous["results"])
        previous["errors"] = sum(r["status"] == "ERROR" for r in previous["results"])
        previous["skipped"] = sum(r["status"] == "SKIP" for r in previous["results"])
        previous["rechecked_at"] = report["executed_at"]
        report = previous
    (TESTS / "checklist_results.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    # Leave a known baseline for browser verification. Only the disposable DB changes.
    if Checklist.baseline:
        xml.restore_database_from_xml(Checklist.baseline)
    db.get_database_service().close()
    db.get_database_service.clear()
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
