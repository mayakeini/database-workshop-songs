import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any
from src.db import get_database_service
from src.queries import db_queries


logger = logging.getLogger(__name__)


def add_text_element(parent: ET.Element, tag: str, value: Any) -> ET.Element:
    """
    Adds a child XML element containing a text value.

    :param parent: Parent XML element.
    :param tag: Name of the child XML element.
    :param value: Value to store inside the element.
    :return: The newly created XML element.
    """
    logger.debug(f"Adding XML element '{tag}'")
    element = ET.SubElement(parent, tag)

    if value is not None:
        if isinstance(value, datetime):
            element.text = value.isoformat()
        else:
            element.text = str(value)

    return element


def get_required_text(parent: ET.Element, tag: str) -> str:
    """
    Reads a required text value from an XML child element.

    :param parent: Parent XML element.
    :param tag: Name of the required child element.
    :return: The text stored in the element.
    """
    element = parent.find(tag)

    if element is None or element.text is None:
        logger.error(f"Required XML element '{tag}' is missing")
        raise ValueError(f"Required XML element '{tag}' is missing.")

    return element.text


def get_optional_text(parent: ET.Element, tag: str) -> str | None:
    """
    Reads an optional text value from an XML child element.

    :param parent: Parent XML element.
    :param tag: Name of the optional child element.
    :return: The stored text, or None if the element is empty or missing.
    """
    element = parent.find(tag)

    if element is None or element.text is None:
        return None

    value = element.text.strip()
    return value if value else None


def export_database_to_xml() -> bytes:
    """
    Exports all project database data into an XML document.
    The backup includes songs, stanzas, words, word occurrences, word groups, group-word relationships, phrases,
    and phrase occurrences.
    :return: UTF-8 encoded XML data.
    """
    logger.info("Starting full database export to XML")

    try:
        with get_database_service().read_cursor() as cursor:
            root = ET.Element("concordance_backup", version="1")
            metadata = ET.SubElement(root,"metadata")
            add_text_element(metadata,"created_at", datetime.now())

            # SONGS
            songs_element = ET.SubElement(root,"songs")
            db_queries.query_select_songs_for_xml_export(cursor)
            songs = cursor.fetchall()

            for (song_id, title, artist, album, publication_year, upload_date) in songs:
                song_element = ET.SubElement(songs_element, "song", id=str(song_id))
                add_text_element(song_element, "title", title)
                add_text_element(song_element, "artist", artist)
                add_text_element(song_element, "album", album)
                add_text_element(song_element, "publication_year", publication_year)
                add_text_element(song_element, "upload_date", upload_date)

            # STANZAS
            stanzas_element = ET.SubElement(root, "stanzas")
            db_queries.query_select_stanzas_for_xml_export(cursor)

            for (stanza_id, song_id, stanza_number) in cursor.fetchall():
                stanza_element = ET.SubElement(stanzas_element, "stanza", id=str(stanza_id))
                add_text_element(stanza_element, "song_id", song_id)
                add_text_element(stanza_element, "stanza_number", stanza_number)

            # WORDS
            words_element = ET.SubElement(root, "words")
            db_queries.query_select_words_for_xml_export(cursor)

            for (word_id, text) in cursor.fetchall():
                word_element = ET.SubElement(words_element, "word", id=str(word_id))
                add_text_element(word_element, "text", text)

            # WORD OCCURRENCES
            occurrences_element = ET.SubElement(root,"word_occurrences")
            db_queries.query_select_word_occurrences_for_xml_export(cursor)

            for row in cursor.fetchall():
                (occurrence_id,
                    word_id,
                    song_id,
                    stanza_id,
                    global_line_number,
                    line_number_in_stanza,
                    position_in_line,
                    position_in_song,
                    original_token,
                ) = row

                occurrence_element = ET.SubElement(occurrences_element, "occurrence", id=str(occurrence_id))
                add_text_element(occurrence_element, "word_id", word_id)
                add_text_element(occurrence_element, "song_id", song_id)
                add_text_element(occurrence_element, "stanza_id", stanza_id)
                add_text_element(occurrence_element, "global_line_number", global_line_number)
                add_text_element(occurrence_element, "line_number_in_stanza", line_number_in_stanza)
                add_text_element(occurrence_element, "position_in_line",position_in_line)
                add_text_element(occurrence_element, "position_in_song", position_in_song)
                add_text_element(occurrence_element, "original_token", original_token)

            # WORD GROUPS
            groups_element = ET.SubElement(root, "word_groups")
            db_queries.query_select_word_groups_for_xml_export(cursor)

            for (group_id, group_name, description, creation_date) in cursor.fetchall():
                group_element = ET.SubElement(groups_element, "group", id=str(group_id))
                add_text_element(group_element, "group_name", group_name)
                add_text_element(group_element, "description", description)
                add_text_element(group_element, "creation_date", creation_date)

            # GROUP WORDS
            group_words_element = ET.SubElement(root, "group_words")
            db_queries.query_select_group_words_for_xml_export(cursor)

            for (group_id, word_id) in cursor.fetchall():
                relation_element = ET.SubElement(group_words_element,"group_word")
                add_text_element(relation_element, "group_id", group_id)
                add_text_element(relation_element, "word_id", word_id)

            # PHRASES
            phrases_element = ET.SubElement(root, "phrases")
            db_queries.query_select_phrases_for_xml_export(cursor)

            for (phrase_id, phrase_name, phrase_text, creation_date) in cursor.fetchall():
                phrase_element = ET.SubElement(phrases_element, "phrase", id=str(phrase_id))
                add_text_element(phrase_element, "phrase_name", phrase_name)
                add_text_element(phrase_element, "phrase_text", phrase_text)
                add_text_element(phrase_element, "creation_date", creation_date)

            # PHRASE OCCURRENCES
            phrase_occurrences_element = ET.SubElement(root, "phrase_occurrences")
            db_queries.query_select_phrase_occurrences_for_xml_export(cursor)

            for row in cursor.fetchall():
                (
                    phrase_occurrence_id,
                    phrase_id,
                    song_id,
                    start_occurrence_id,
                    end_occurrence_id,
                ) = row

                phrase_occurrence_element = ET.SubElement(
                    phrase_occurrences_element,
                    "phrase_occurrence",
                    id=str(phrase_occurrence_id)
                )
                add_text_element(phrase_occurrence_element, "phrase_id", phrase_id)
                add_text_element(phrase_occurrence_element, "song_id", song_id)
                add_text_element(phrase_occurrence_element, "start_occurrence_id", start_occurrence_id)
                add_text_element(phrase_occurrence_element, "end_occurrence_id", end_occurrence_id)

            ET.indent(root, space="  ")
            xml_data = ET.tostring(root, encoding="utf-8", xml_declaration=True)

            logger.info("Database XML export completed successfully")
            return xml_data

    except Exception as e:
        logger.error(f"Failed to export database to XML due to {e}")
        raise


def import_database_from_xml(xml_data: bytes) -> dict[str, int]:
    """
    Replaces the current project database contents with data from a concordance XML backup.
    Existing project data is deleted first. New database IDs are generated during restoration, while internal
    relationships are rebuilt using mappings between the old XML IDs and new Oracle IDs.
    :param xml_data: XML backup content as bytes.
    :return: A dictionary containing the number of restored records for each major entity.
    """
    logger.info("Starting database restoration from XML")

    try:
        root = ET.fromstring(xml_data)

    except ET.ParseError:
        logger.error("Uploaded XML could not be parsed")
        raise ValueError("The uploaded file is not valid XML.")

    if root.tag != "concordance_backup":
        logger.error(f'Invalid XML root element: {root.tag}')
        raise ValueError("The XML file is not a concordance backup.")

    required_sections = [
        "songs",
        "stanzas",
        "words",
        "word_occurrences",
        "word_groups",
        "group_words",
        "phrases",
        "phrase_occurrences"
    ]

    for section_name in required_sections:
        if root.find(section_name) is None:
            logger.error(f"Required XML section '{section_name}' is missing")
            raise ValueError(f"Required XML section '{section_name}' is missing."
            )

    counts: dict[str, int] = {
        "songs": 0,
        "stanzas": 0,
        "words": 0,
        "word_occurrences": 0,
        "word_groups": 0,
        "group_words": 0,
        "phrases": 0,
        "phrase_occurrences": 0,
    }

    song_map: dict[int, int] = {}
    stanza_map: dict[int, int] = {}
    word_map: dict[int, int] = {}
    group_map: dict[int, int] = {}
    phrase_map: dict[int, int] = {}
    occurrence_map: dict[int, int] = {}

    try:
        with get_database_service().transaction() as cursor:
            logger.info("Deleting current project data before XML restore")

            delete_order = [
                "phrase_occurrences",
                "group_words",
                "word_occurrences",
                "phrases",
                "word_groups",
                "stanzas",
                "words",
                "songs",
            ]

            for table_name in delete_order:
                db_queries.query_delete_table_data(cursor, table_name)

            # SONGS
            songs_section = root.find("songs")

            if songs_section is None:
                raise ValueError("Required XML section 'songs' is missing.")

            for song in songs_section.findall("song"):
                old_id = int(song.attrib["id"])
                new_id_var = cursor.var(int)
                upload_date_text = get_required_text(song, "upload_date")

                db_queries.query_insert_song_returning_id(
                    cursor,
                    title=get_required_text(song, "title"),
                    artist=get_required_text(song, "artist"),
                    album=get_optional_text(song, "album"),
                    publication_year=int(get_required_text(song,"publication_year")),
                    upload_date=datetime.fromisoformat(upload_date_text),
                    song_id=new_id_var
                )

                song_map[old_id] = new_id_var.getvalue()[0]
                counts["songs"] += 1

            # STANZAS
            stanzas_section = root.find("stanzas")

            if stanzas_section is None:
                raise ValueError("Required XML section 'stanzas' is missing.")

            for stanza in stanzas_section.findall("stanza"):
                old_id = int(stanza.attrib["id"])
                old_song_id = int(get_required_text(stanza, "song_id"))
                new_id_var = cursor.var(int)
                db_queries.query_insert_stanza_returning_id(
                    cursor,
                    song_id=song_map[old_song_id],
                    stanza_number=int(get_required_text(stanza, "stanza_number")),
                    stanza_id=new_id_var
                )
                stanza_map[old_id] = new_id_var.getvalue()[0]
                counts["stanzas"] += 1

            # WORDS
            words_section = root.find("words")

            if words_section is None:
                raise ValueError("Required XML section 'words' is missing.")

            for word in words_section.findall("word"):
                old_id = int(word.attrib["id"])
                new_id_var = cursor.var(int)
                db_queries.query_insert_word_returning_id(
                    cursor,
                    word=get_required_text(word, "text"),
                    word_id=new_id_var,
                )

                word_map[old_id] = new_id_var.getvalue()[0]
                counts["words"] += 1

            # WORD OCCURRENCES
            occurrences_section = root.find("word_occurrences")

            if occurrences_section is None:
                raise ValueError("Required XML section 'word_occurrences' is missing.")

            for occurrence in occurrences_section.findall("occurrence"):
                old_occurrence_id = int(occurrence.attrib["id"])
                old_word_id = int(get_required_text(occurrence, "word_id"))
                old_song_id = int(get_required_text(occurrence, "song_id"))
                old_stanza_id = int(get_required_text(occurrence, "stanza_id"))
                new_id_var = cursor.var(int)
                db_queries.query_insert_word_occurrence_for_xml_restore(
                    cursor,
                    word_id=word_map[old_word_id],
                    song_id=song_map[old_song_id],
                    stanza_id=stanza_map[old_stanza_id],
                    global_line_number=int(get_required_text(occurrence, "global_line_number")),
                    line_number_in_stanza=int(get_required_text(occurrence, "line_number_in_stanza")),
                    position_in_line=int(get_required_text(occurrence, "position_in_line")),
                    position_in_song=int(get_required_text(occurrence, "position_in_song")),
                    original_token=get_required_text(occurrence, "original_token"),
                    occurrence_id=new_id_var
                )

                occurrence_map[old_occurrence_id] = new_id_var.getvalue()[0]
                counts["word_occurrences"] += 1

            # WORD GROUPS
            groups_section = root.find("word_groups")

            if groups_section is None:
                raise ValueError("Required XML section 'word_groups' is missing.")

            for group in groups_section.findall("group"):
                old_id = int(group.attrib["id"])
                new_id_var = cursor.var(int)
                creation_date_text = get_required_text(group, "creation_date")
                db_queries.query_insert_word_group_for_xml_restore(
                    cursor,
                    group_name=get_required_text(group, "group_name"),
                    description=get_optional_text(group, "description"),
                    creation_date=datetime.fromisoformat(creation_date_text),
                    group_id=new_id_var
                )

                group_map[old_id] = new_id_var.getvalue()[0]
                counts["word_groups"] += 1

            # GROUP WORDS
            group_words_section = root.find("group_words")

            if group_words_section is None:
                raise ValueError("Required XML section 'group_words' is missing.")

            for relation in group_words_section.findall("group_word"):
                old_group_id = int(get_required_text(relation, "group_id"))
                old_word_id = int(get_required_text(relation, "word_id"))
                db_queries.query_insert_group_word(
                    cursor,
                    group_id=group_map[old_group_id],
                    word_id=word_map[old_word_id]
                )

                counts["group_words"] += 1

            # PHRASES
            phrases_section = root.find("phrases")

            if phrases_section is None:
                raise ValueError("Required XML section 'phrases' is missing.")

            for phrase in phrases_section.findall("phrase"):
                old_id = int(phrase.attrib["id"])
                new_id_var = cursor.var(int)
                creation_date_text = get_required_text(phrase, "creation_date")

                db_queries.query_insert_phrase_for_xml_restore(
                    cursor,
                    phrase_name=get_required_text(phrase, "phrase_name"),
                    phrase_text=get_required_text(phrase, "phrase_text"),
                    creation_date=datetime.fromisoformat(creation_date_text),
                    phrase_id=new_id_var
                )

                phrase_map[old_id] = new_id_var.getvalue()[0]
                counts["phrases"] += 1

            # PHRASE OCCURRENCES
            phrase_occurrences_section = root.find("phrase_occurrences")

            if phrase_occurrences_section is None:
                raise ValueError("Required XML section 'phrase_occurrences' is missing.")

            for occurrence in phrase_occurrences_section.findall("phrase_occurrence"):
                old_phrase_id = int(get_required_text(occurrence, "phrase_id"))
                old_song_id = int(get_required_text(occurrence, "song_id"))
                old_start_id = int(get_required_text(occurrence, "start_occurrence_id"))
                old_end_id = int(get_required_text(occurrence, "end_occurrence_id"))

                db_queries.query_insert_phrase_occurrence(
                    cursor,
                    phrase_id=phrase_map[old_phrase_id],
                    song_id=song_map[old_song_id],
                    start_occurrence_id=occurrence_map[old_start_id],
                    end_occurrence_id=occurrence_map[old_end_id]
                )

                counts["phrase_occurrences"] += 1

        logger.info(f'Database restoration completed successfully: {counts}')
        return counts

    except Exception as e:
        logger.error("Database restoration failed.")
        raise
