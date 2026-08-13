import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

from src.db import get_connection

logger = logging.getLogger(__name__)


def _add_text_element(
    parent: ET.Element,
    tag: str,
    value: Any,
) -> ET.Element:
    """
    Adds a child XML element containing a text value.

    Args:
        parent: Parent XML element.
        tag: Name of the child XML element.
        value: Value to store inside the element.

    Returns:
        The newly created XML element.
    """
    logger.debug(
        "Adding XML element '%s'",
        tag,
    )

    element = ET.SubElement(
        parent,
        tag,
    )

    if value is not None:
        if isinstance(value, datetime):
            element.text = value.isoformat()
        else:
            element.text = str(value)

    return element


def _get_required_text(
    parent: ET.Element,
    tag: str,
) -> str:
    """
    Reads a required text value from an XML child element.

    Args:
        parent: Parent XML element.
        tag: Name of the required child element.

    Returns:
        The text stored in the element.

    Raises:
        ValueError: If the element or its text is missing.
    """
    element = parent.find(tag)

    if element is None or element.text is None:
        logger.error(
            "Required XML element '%s' is missing",
            tag,
        )

        raise ValueError(
            f"Required XML element '{tag}' is missing."
        )

    return element.text


def _get_optional_text(
    parent: ET.Element,
    tag: str,
) -> str | None:
    """
    Reads an optional text value from an XML child element.

    Args:
        parent: Parent XML element.
        tag: Name of the optional child element.

    Returns:
        The stored text, or None if the element is empty or missing.
    """
    element = parent.find(tag)

    if element is None or element.text is None:
        return None

    value = element.text.strip()

    return value if value else None


def export_database_to_xml() -> bytes:
    """
    Exports all project database data into an XML document.

    The backup includes songs, stanzas, words, word occurrences,
    word groups, group-word relationships, phrases, and phrase
    occurrences.

    Returns:
        UTF-8 encoded XML data.

    Raises:
        Exception: If reading from the database or creating
            the XML document fails.
    """
    logger.info(
        "Starting full database export to XML"
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        root = ET.Element(
            "concordance_backup",
            version="1",
        )

        metadata = ET.SubElement(
            root,
            "metadata",
        )

        _add_text_element(
            metadata,
            "created_at",
            datetime.now(),
        )

        # SONGS
        songs_element = ET.SubElement(
            root,
            "songs",
        )

        cursor.execute(
            """
            SELECT
                song_id,
                title,
                artist,
                album,
                publication_year,
                TO_CHAR(
                    upload_date,
                    'YYYY-MM-DD HH24:MI:SS TZH:TZM'
                ) AS upload_date
            FROM songs
            ORDER BY song_id
            """
        )

        songs = cursor.fetchall()

        for (
            song_id,
            title,
            artist,
            album,
            publication_year,
            upload_date,
        ) in songs:
            song_element = ET.SubElement(
                songs_element,
                "song",
                id=str(song_id),
            )

            _add_text_element(
                song_element,
                "title",
                title,
            )

            _add_text_element(
                song_element,
                "artist",
                artist,
            )

            _add_text_element(
                song_element,
                "album",
                album,
            )

            _add_text_element(
                song_element,
                "publication_year",
                publication_year,
            )

            _add_text_element(
                song_element,
                "upload_date",
                upload_date,
            )

        # STANZAS
        stanzas_element = ET.SubElement(
            root,
            "stanzas",
        )

        cursor.execute(
            """
            SELECT
                stanza_id,
                song_id,
                stanza_number
            FROM stanzas
            ORDER BY stanza_id
            """
        )

        for (
            stanza_id,
            song_id,
            stanza_number,
        ) in cursor.fetchall():
            stanza_element = ET.SubElement(
                stanzas_element,
                "stanza",
                id=str(stanza_id),
            )

            _add_text_element(
                stanza_element,
                "song_id",
                song_id,
            )

            _add_text_element(
                stanza_element,
                "stanza_number",
                stanza_number,
            )

        # WORDS
        words_element = ET.SubElement(
            root,
            "words",
        )

        cursor.execute(
            """
            SELECT
                word_id,
                text
            FROM words
            ORDER BY word_id
            """
        )

        for (
            word_id,
            text,
        ) in cursor.fetchall():
            word_element = ET.SubElement(
                words_element,
                "word",
                id=str(word_id),
            )

            _add_text_element(
                word_element,
                "text",
                text,
            )

        # WORD OCCURRENCES
        occurrences_element = ET.SubElement(
            root,
            "word_occurrences",
        )

        cursor.execute(
            """
            SELECT
                occurrence_id,
                word_id,
                song_id,
                stanza_id,
                global_line_number,
                line_number_in_stanza,
                position_in_line,
                position_in_song,
                original_token
            FROM word_occurrences
            ORDER BY occurrence_id
            """
        )

        for row in cursor.fetchall():
            (
                occurrence_id,
                word_id,
                song_id,
                stanza_id,
                global_line_number,
                line_number_in_stanza,
                position_in_line,
                position_in_song,
                original_token,
            ) = row

            occurrence_element = ET.SubElement(
                occurrences_element,
                "occurrence",
                id=str(occurrence_id),
            )

            _add_text_element(
                occurrence_element,
                "word_id",
                word_id,
            )

            _add_text_element(
                occurrence_element,
                "song_id",
                song_id,
            )

            _add_text_element(
                occurrence_element,
                "stanza_id",
                stanza_id,
            )

            _add_text_element(
                occurrence_element,
                "global_line_number",
                global_line_number,
            )

            _add_text_element(
                occurrence_element,
                "line_number_in_stanza",
                line_number_in_stanza,
            )

            _add_text_element(
                occurrence_element,
                "position_in_line",
                position_in_line,
            )

            _add_text_element(
                occurrence_element,
                "position_in_song",
                position_in_song,
            )

            _add_text_element(
                occurrence_element,
                "original_token",
                original_token,
            )

        # WORD GROUPS
        groups_element = ET.SubElement(
            root,
            "word_groups",
        )

        cursor.execute(
            """
            SELECT
                group_id,
                group_name,
                description,
                TO_CHAR(
                    creation_date,
                    'YYYY-MM-DD HH24:MI:SS TZH:TZM'
                ) AS creation_date
            FROM word_groups
            ORDER BY group_id
            """
        )

        for (
            group_id,
            group_name,
            description,
            creation_date,
        ) in cursor.fetchall():
            group_element = ET.SubElement(
                groups_element,
                "group",
                id=str(group_id),
            )

            _add_text_element(
                group_element,
                "group_name",
                group_name,
            )

            _add_text_element(
                group_element,
                "description",
                description,
            )

            _add_text_element(
                group_element,
                "creation_date",
                creation_date,
            )

        # GROUP WORDS
        group_words_element = ET.SubElement(
            root,
            "group_words",
        )

        cursor.execute(
            """
            SELECT
                group_id,
                word_id
            FROM group_words
            ORDER BY
                group_id,
                word_id
            """
        )

        for (
            group_id,
            word_id,
        ) in cursor.fetchall():
            relation_element = ET.SubElement(
                group_words_element,
                "group_word",
            )

            _add_text_element(
                relation_element,
                "group_id",
                group_id,
            )

            _add_text_element(
                relation_element,
                "word_id",
                word_id,
            )

        # PHRASES
        phrases_element = ET.SubElement(
            root,
            "phrases",
        )

        cursor.execute(
            """
            SELECT
                phrase_id,
                phrase_name,
                phrase_text,
                TO_CHAR(
                    creation_date,
                    'YYYY-MM-DD HH24:MI:SS TZH:TZM'
                ) AS creation_date
            FROM phrases
            ORDER BY phrase_id
            """
        )

        for (
            phrase_id,
            phrase_name,
            phrase_text,
            creation_date,
        ) in cursor.fetchall():
            phrase_element = ET.SubElement(
                phrases_element,
                "phrase",
                id=str(phrase_id),
            )

            _add_text_element(
                phrase_element,
                "phrase_name",
                phrase_name,
            )

            _add_text_element(
                phrase_element,
                "phrase_text",
                phrase_text,
            )

            _add_text_element(
                phrase_element,
                "creation_date",
                creation_date,
            )

        # PHRASE OCCURRENCES
        phrase_occurrences_element = ET.SubElement(
            root,
            "phrase_occurrences",
        )

        cursor.execute(
            """
            SELECT
                phrase_occurrence_id,
                phrase_id,
                song_id,
                start_occurrence_id,
                end_occurrence_id
            FROM phrase_occurrences
            ORDER BY phrase_occurrence_id
            """
        )

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
                id=str(phrase_occurrence_id),
            )

            _add_text_element(
                phrase_occurrence_element,
                "phrase_id",
                phrase_id,
            )

            _add_text_element(
                phrase_occurrence_element,
                "song_id",
                song_id,
            )

            _add_text_element(
                phrase_occurrence_element,
                "start_occurrence_id",
                start_occurrence_id,
            )

            _add_text_element(
                phrase_occurrence_element,
                "end_occurrence_id",
                end_occurrence_id,
            )

        ET.indent(
            root,
            space="  ",
        )

        xml_data = ET.tostring(
            root,
            encoding="utf-8",
            xml_declaration=True,
        )

        logger.info(
            "Database XML export completed successfully"
        )

        return xml_data

    except Exception:
        logger.exception(
            "Failed to export database to XML"
        )
        raise

    finally:
        connection.close()


def restore_database_from_xml(
    xml_data: bytes,
) -> dict[str, int]:
    """
    Replaces the current project database contents with data from
    a concordance XML backup.

    Existing project data is deleted first. New database IDs are
    generated during restoration, while internal relationships are
    rebuilt using mappings between the old XML IDs and new Oracle IDs.

    Args:
        xml_data: XML backup content as bytes.

    Returns:
        A dictionary containing the number of restored records
        for each major entity.

    Raises:
        ValueError: If the XML structure is invalid.
        Exception: If restoring the database fails.
    """
    logger.info(
        "Starting database restoration from XML"
    )

    try:
        root = ET.fromstring(
            xml_data
        )

    except ET.ParseError as error:
        logger.exception(
            "Uploaded XML could not be parsed"
        )

        raise ValueError(
            "The uploaded file is not valid XML."
        ) from error

    if root.tag != "concordance_backup":
        logger.error(
            "Invalid XML root element: %s",
            root.tag,
        )

        raise ValueError(
            "The XML file is not a concordance backup."
        )

    required_sections = [
        "songs",
        "stanzas",
        "words",
        "word_occurrences",
        "word_groups",
        "group_words",
        "phrases",
        "phrase_occurrences",
    ]

    for section_name in required_sections:
        if root.find(section_name) is None:
            logger.error(
                "Required XML section '%s' is missing",
                section_name,
            )

            raise ValueError(
                f"Required XML section "
                f"'{section_name}' is missing."
            )

    connection = get_connection()

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
        cursor = connection.cursor()

        logger.info(
            "Deleting current project data before XML restore"
        )

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
            cursor.execute(
                f"DELETE FROM {table_name}"
            )

        # SONGS
        songs_section = root.find(
            "songs"
        )

        if songs_section is None:
            raise ValueError(
                "Required XML section 'songs' is missing."
            )

        for song in songs_section.findall(
            "song"
        ):
            old_id = int(
                song.attrib["id"]
            )

            new_id_var = cursor.var(int)

            upload_date_text = _get_required_text(
                song,
                "upload_date",
            )

            cursor.execute(
                """
                INSERT INTO songs (
                    title,
                    artist,
                    album,
                    publication_year,
                    upload_date
                )
                VALUES (
                    :title,
                    :artist,
                    :album,
                    :publication_year,
                    :upload_date
                )
                RETURNING song_id INTO :song_id
                """,
                title=_get_required_text(
                    song,
                    "title",
                ),
                artist=_get_required_text(
                    song,
                    "artist",
                ),
                album=_get_optional_text(
                    song,
                    "album",
                ),
                publication_year=int(
                    _get_required_text(
                        song,
                        "publication_year",
                    )
                ),
                upload_date=datetime.fromisoformat(
                    upload_date_text
                ),
                song_id=new_id_var,
            )

            song_map[
                old_id
            ] = new_id_var.getvalue()[0]

            counts["songs"] += 1

        # STANZAS
        stanzas_section = root.find(
            "stanzas"
        )

        if stanzas_section is None:
            raise ValueError(
                "Required XML section 'stanzas' is missing."
            )

        for stanza in stanzas_section.findall(
            "stanza"
        ):
            old_id = int(
                stanza.attrib["id"]
            )

            old_song_id = int(
                _get_required_text(
                    stanza,
                    "song_id",
                )
            )

            new_id_var = cursor.var(int)

            cursor.execute(
                """
                INSERT INTO stanzas (
                    song_id,
                    stanza_number
                )
                VALUES (
                    :song_id,
                    :stanza_number
                )
                RETURNING stanza_id INTO :stanza_id
                """,
                song_id=song_map[
                    old_song_id
                ],
                stanza_number=int(
                    _get_required_text(
                        stanza,
                        "stanza_number",
                    )
                ),
                stanza_id=new_id_var,
            )

            stanza_map[
                old_id
            ] = new_id_var.getvalue()[0]

            counts["stanzas"] += 1

        # WORDS
        words_section = root.find(
            "words"
        )

        if words_section is None:
            raise ValueError(
                "Required XML section 'words' is missing."
            )

        for word in words_section.findall(
            "word"
        ):
            old_id = int(
                word.attrib["id"]
            )

            new_id_var = cursor.var(int)

            cursor.execute(
                """
                INSERT INTO words (
                    text
                )
                VALUES (
                    :text
                )
                RETURNING word_id INTO :word_id
                """,
                text=_get_required_text(
                    word,
                    "text",
                ),
                word_id=new_id_var,
            )

            word_map[
                old_id
            ] = new_id_var.getvalue()[0]

            counts["words"] += 1

        # WORD OCCURRENCES
        occurrences_section = root.find(
            "word_occurrences"
        )

        if occurrences_section is None:
            raise ValueError(
                "Required XML section "
                "'word_occurrences' is missing."
            )

        for occurrence in occurrences_section.findall(
            "occurrence"
        ):
            old_occurrence_id = int(
                occurrence.attrib["id"]
            )

            old_word_id = int(
                _get_required_text(
                    occurrence,
                    "word_id",
                )
            )

            old_song_id = int(
                _get_required_text(
                    occurrence,
                    "song_id",
                )
            )

            old_stanza_id = int(
                _get_required_text(
                    occurrence,
                    "stanza_id",
                )
            )

            new_id_var = cursor.var(int)

            cursor.execute(
                """
                INSERT INTO word_occurrences (
                    word_id,
                    song_id,
                    stanza_id,
                    global_line_number,
                    line_number_in_stanza,
                    position_in_line,
                    position_in_song,
                    original_token
                )
                VALUES (
                    :word_id,
                    :song_id,
                    :stanza_id,
                    :global_line_number,
                    :line_number_in_stanza,
                    :position_in_line,
                    :position_in_song,
                    :original_token
                )
                RETURNING occurrence_id INTO :occurrence_id
                """,
                word_id=word_map[
                    old_word_id
                ],
                song_id=song_map[
                    old_song_id
                ],
                stanza_id=stanza_map[
                    old_stanza_id
                ],
                global_line_number=int(
                    _get_required_text(
                        occurrence,
                        "global_line_number",
                    )
                ),
                line_number_in_stanza=int(
                    _get_required_text(
                        occurrence,
                        "line_number_in_stanza",
                    )
                ),
                position_in_line=int(
                    _get_required_text(
                        occurrence,
                        "position_in_line",
                    )
                ),
                position_in_song=int(
                    _get_required_text(
                        occurrence,
                        "position_in_song",
                    )
                ),
                original_token=_get_required_text(
                    occurrence,
                    "original_token",
                ),
                occurrence_id=new_id_var,
            )

            occurrence_map[
                old_occurrence_id
            ] = new_id_var.getvalue()[0]

            counts[
                "word_occurrences"
            ] += 1

        # WORD GROUPS
        groups_section = root.find(
            "word_groups"
        )

        if groups_section is None:
            raise ValueError(
                "Required XML section "
                "'word_groups' is missing."
            )

        for group in groups_section.findall(
            "group"
        ):
            old_id = int(
                group.attrib["id"]
            )

            new_id_var = cursor.var(int)

            creation_date_text = _get_required_text(
                group,
                "creation_date",
            )

            cursor.execute(
                """
                INSERT INTO word_groups (
                    group_name,
                    description,
                    creation_date
                )
                VALUES (
                    :group_name,
                    :description,
                    :creation_date
                )
                RETURNING group_id INTO :group_id
                """,
                group_name=_get_required_text(
                    group,
                    "group_name",
                ),
                description=_get_optional_text(
                    group,
                    "description",
                ),
                creation_date=datetime.fromisoformat(
                    creation_date_text
                ),
                group_id=new_id_var,
            )

            group_map[
                old_id
            ] = new_id_var.getvalue()[0]

            counts["word_groups"] += 1

        # GROUP WORDS
        group_words_section = root.find(
            "group_words"
        )

        if group_words_section is None:
            raise ValueError(
                "Required XML section "
                "'group_words' is missing."
            )

        for relation in group_words_section.findall(
            "group_word"
        ):
            old_group_id = int(
                _get_required_text(
                    relation,
                    "group_id",
                )
            )

            old_word_id = int(
                _get_required_text(
                    relation,
                    "word_id",
                )
            )

            cursor.execute(
                """
                INSERT INTO group_words (
                    group_id,
                    word_id
                )
                VALUES (
                    :group_id,
                    :word_id
                )
                """,
                group_id=group_map[
                    old_group_id
                ],
                word_id=word_map[
                    old_word_id
                ],
            )

            counts["group_words"] += 1

        # PHRASES
        phrases_section = root.find(
            "phrases"
        )

        if phrases_section is None:
            raise ValueError(
                "Required XML section 'phrases' is missing."
            )

        for phrase in phrases_section.findall(
            "phrase"
        ):
            old_id = int(
                phrase.attrib["id"]
            )

            new_id_var = cursor.var(int)

            creation_date_text = _get_required_text(
                phrase,
                "creation_date",
            )

            cursor.execute(
                """
                INSERT INTO phrases (
                    phrase_name,
                    phrase_text,
                    creation_date
                )
                VALUES (
                    :phrase_name,
                    :phrase_text,
                    :creation_date
                )
                RETURNING phrase_id INTO :phrase_id
                """,
                phrase_name=_get_required_text(
                    phrase,
                    "phrase_name",
                ),
                phrase_text=_get_required_text(
                    phrase,
                    "phrase_text",
                ),
                creation_date=datetime.fromisoformat(
                    creation_date_text
                ),
                phrase_id=new_id_var,
            )

            phrase_map[
                old_id
            ] = new_id_var.getvalue()[0]

            counts["phrases"] += 1

        # PHRASE OCCURRENCES
        phrase_occurrences_section = root.find(
            "phrase_occurrences"
        )

        if phrase_occurrences_section is None:
            raise ValueError(
                "Required XML section "
                "'phrase_occurrences' is missing."
            )

        for occurrence in phrase_occurrences_section.findall(
            "phrase_occurrence"
        ):
            old_phrase_id = int(
                _get_required_text(
                    occurrence,
                    "phrase_id",
                )
            )

            old_song_id = int(
                _get_required_text(
                    occurrence,
                    "song_id",
                )
            )

            old_start_id = int(
                _get_required_text(
                    occurrence,
                    "start_occurrence_id",
                )
            )

            old_end_id = int(
                _get_required_text(
                    occurrence,
                    "end_occurrence_id",
                )
            )

            cursor.execute(
                """
                INSERT INTO phrase_occurrences (
                    phrase_id,
                    song_id,
                    start_occurrence_id,
                    end_occurrence_id
                )
                VALUES (
                    :phrase_id,
                    :song_id,
                    :start_occurrence_id,
                    :end_occurrence_id
                )
                """,
                phrase_id=phrase_map[
                    old_phrase_id
                ],
                song_id=song_map[
                    old_song_id
                ],
                start_occurrence_id=occurrence_map[
                    old_start_id
                ],
                end_occurrence_id=occurrence_map[
                    old_end_id
                ],
            )

            counts[
                "phrase_occurrences"
            ] += 1

        connection.commit()

        logger.info(
            "Database restoration completed "
            "successfully: %s",
            counts,
        )

        return counts

    except Exception:
        connection.rollback()

        logger.exception(
            "Database restoration failed. "
            "All changes were rolled back."
        )

        raise

    finally:
        connection.close()
