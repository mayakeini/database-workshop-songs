"""Helpers for the opt-in checklist against the disposable Oracle on port 1522.

No production functions are replaced except explicit failure/race injection in
individual white-box cases. Streamlit's AppTest exercises real page widgets.
"""
from pathlib import Path
from unittest.mock import patch
import csv
import io
import json
import logging
import os
import tempfile
import time
import xml.etree.ElementTree as ET

import oracledb
import streamlit as st
from streamlit.testing.v1 import AppTest
from src import db, song_service, xml_service

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "sample_songs"
TESTS = ROOT / "tests"
CONTAINER = "songs-checklist-test-20261027"
TABLES = ("songs", "stanzas", "words", "word_occurrences", "word_groups",
          "group_words", "phrases", "phrase_occurrences")
FILES = [
    ("example.txt", "Example", "Test Artist", 2, 4, 16, 13),
    ("Hallelujah – Leonard Cohen.txt", "Hallelujah", "Leonard Cohen", 10, 59, 301, 148),
    ("Don’t Stop Me Now – Queen.txt", "Don’t Stop Me Now", "Queen", 7, 55, 367, 105),
    ("I will always love you - Whitney Houston.txt", "I Will Always Love You", "Whitney Houston", 8, 32, 157, 63),
    ("Let It Be – The Beatles.txt", "Let It Be", "The Beatles", 3, 39, 271, 65),
    ("Lover To Lover - Florence + the Machine.txt", "Lover To Lover", "Florence + the Machine", 10, 57, 261, 55),
    ("My Heart Will Go On - Celine Dion.txt", "My Heart Will Go On", "Celine Dion", 4, 28, 179, 73),
    ("Someone Like You – Adele.txt", "Someone Like You", "Adele", 10, 39, 330, 120),
    ("happy - Pharrell Williams.txt", "Happy", "Pharrell Williams", 12, 63, 497, 99),
]
PAGES = ["app.py"] + [str(p.relative_to(ROOT)) for p in sorted((ROOT / "pages").glob("*.py"))]
TEMP_PATHS = []
_named_temp = tempfile.NamedTemporaryFile


def temp_in_allowed_directory(*args, **kwargs):
    kwargs["dir"] = str(SAMPLES if kwargs.get("suffix") == ".txt" else TESTS)
    result = _named_temp(*args, **kwargs)
    TEMP_PATHS.append(result.name)
    return result


def run(at):
    downloads = []
    charts = []
    original_download = st.download_button
    original_chart = st.altair_chart
    def capture_download(*args, **kwargs):
        downloads.append(kwargs.get("data", args[1] if len(args) > 1 else None))
        return original_download(*args, **kwargs)
    def capture_chart(chart, *args, **kwargs):
        charts.append(chart.to_dict())
        return original_chart(chart, *args, **kwargs)
    with patch.object(tempfile, "NamedTemporaryFile", side_effect=temp_in_allowed_directory), \
         patch.object(st, "download_button", side_effect=capture_download), \
         patch.object(st, "altair_chart", side_effect=capture_chart):
        at.run(timeout=40)
    at._checklist_downloads = downloads
    at._checklist_charts = charts
    if len(at.exception):
        raise AssertionError("Unhandled UI exception: " + "; ".join(str(x.value) for x in at.exception))
    return at


def page(path):
    return run(AppTest.from_file(str(ROOT / path), default_timeout=40))


def button(at, label):
    matches = [b for b in at.button if b.label == label]
    if len(matches) != 1:
        raise AssertionError(f"Expected one button {label!r}, got {[b.label for b in at.button]}")
    return matches[0]


def click(at, label):
    button(at, label).click()
    return run(at)


def texts(elements):
    return "\n".join(str(x.value) for x in elements)


def upload(index=0, title=None, artist=None, year=2000, album="", submit=True):
    filename, default_title, default_artist, *_ = FILES[index]
    at = page("pages/1_upload_song.py")
    at.text_input(key="song_title").set_value(default_title if title is None else title)
    at.text_input(key="song_artist").set_value(default_artist if artist is None else artist)
    at.text_input(key="song_album").set_value(album)
    at.number_input(key="song_publication_year").set_value(year)
    at.file_uploader[0].set_value((filename, (SAMPLES / filename).read_bytes(), "text/plain"))
    if submit:
        click(at, "Upload Song")
    return at


def metrics(at):
    return {x.label: x.value for x in at.metric}


def query(sql, **params):
    with db.get_database_service().read_cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def counts():
    return {t: query(f"SELECT COUNT(*) FROM {t}")[0][0] for t in TABLES}


def raw_snapshot():
    return {t: query(f"SELECT * FROM {t} ORDER BY 1, 2") for t in TABLES}


def semantic_snapshot():
    """Capture all XML data and relationships, independent of regenerated IDs."""
    root = ET.fromstring(xml_service.export_database_to_xml())
    maps = {}
    for section, tag in (("songs", "song"), ("stanzas", "stanza"), ("words", "word"),
                         ("word_occurrences", "occurrence"), ("word_groups", "group"),
                         ("phrases", "phrase")):
        maps[section] = {}
        for element in root.find(section):
            values = []
            for child in element:
                text = child.text
                references = {"song_id": "songs", "stanza_id": "stanzas", "word_id": "words"}
                if child.tag in references:
                    text = maps[references[child.tag]][text]
                values.append((child.tag, text))
            maps[section][element.attrib["id"]] = tuple(values)
    result = {section: sorted(values.values(), key=repr) for section, values in maps.items()}
    result["group_words"] = sorted([(maps["word_groups"][e.findtext("group_id")],
                                      maps["words"][e.findtext("word_id")])
                                     for e in root.find("group_words")], key=repr)
    result["phrase_occurrences"] = sorted([
        (maps["phrases"][e.findtext("phrase_id")], maps["songs"][e.findtext("song_id")],
         maps["word_occurrences"][e.findtext("start_occurrence_id")],
         maps["word_occurrences"][e.findtext("end_occurrence_id")])
        for e in root.find("phrase_occurrences")], key=repr)
    return result


def song_id(title="Example"):
    return query("SELECT song_id FROM songs WHERE title=:title", title=title)[0][0]


def create_phrase_ui(name, text):
    at = page("pages/5_phrases.py")
    at.text_input(key="new_phrase_name").set_value(name)
    at.text_input(key="new_phrase_text").set_value(text)
    click(at, "Create and Search Phrase")
    return at


def create_group_ui(name="Selected Words", first="love"):
    at = page("pages/4_word_groups.py")
    at.text_input(key="new_group_name_0").set_value(name)
    at.text_input(key="new_group_first_word_0").set_value(first)
    click(at, "Create Group")
    return at


def restore_ui(data, confirm=True):
    at = page("pages/7_backup_restore.py")
    at.file_uploader[0].set_value(("checklist.xml", data, "application/xml"))
    at.checkbox(key="confirm_xml_restore").set_value(confirm)
    run(at)
    if confirm:
        click(at, "Restore Database")
    return at


def setup_database():
    if os.environ.get("RUN_MANUAL_CHECKLIST") != "1" or os.environ.get("ORACLE_PORT") != "1522":
        raise RuntimeError("Requires RUN_MANUAL_CHECKLIST=1 and ORACLE_PORT=1522 (disposable database only)")
    if os.environ.get("ORACLE_HOST", "localhost") not in ("localhost", "127.0.0.1"):
        raise RuntimeError("This suite only permits the local disposable database")
    os.environ["ORACLE_USER"] = "concordance"
    os.environ["ORACLE_PASSWORD"] = "songsproject"
    os.environ["ORACLE_SERVICE"] = "FREEPDB1"
    db.get_database_service.clear()
    with oracledb.connect(user="concordance", password="songsproject", dsn="localhost:1522/FREEPDB1") as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM user_tables")
            if cursor.fetchone()[0] == 0:
                for statement in (ROOT / "schema.sql").read_text().split(";"):
                    if statement.strip():
                        cursor.execute(statement)
    # Only the explicitly opted-in, disposable port is ever cleared.
    with db.get_database_service().transaction() as cursor:
        for table in ("phrase_occurrences", "group_words", "word_occurrences", "phrases",
                      "word_groups", "stanzas", "words", "songs"):
            cursor.execute(f"DELETE FROM {table}")


def csv_rows_from_button(at):
    """Read the actual CSV payload passed to the rendered download widget."""
    content = at._checklist_downloads[0]
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    return list(csv.DictReader(io.StringIO(content)))
