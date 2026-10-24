import logging
import oracledb

logger = logging.getLogger(__name__)


# Session setup


def query_set_session_timezone(cursor):
    cursor.execute(
        "ALTER SESSION SET TIME_ZONE = '+03:00'"
    )


# Shared word and occurrence queries


def query_select_word_id_by_text(cursor, word: str):
    cursor.execute(
        """
        SELECT word_id
        FROM words
        WHERE text = :word
        """,
        word=word,
    )


def query_insert_word_returning_id(cursor, word: str, word_id):
    cursor.execute(
        """
        INSERT INTO words (
            text
        )
        VALUES (
            :word
        )
        RETURNING word_id INTO :word_id
        """,
        word=word,
        word_id=word_id,
    )


def query_insert_group_word(cursor, group_id: int, word_id: int):
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
        group_id=group_id,
        word_id=word_id,
    )


def query_insert_phrase_occurrence(
    cursor,
    phrase_id: int,
    song_id: int,
    start_occurrence_id: int,
    end_occurrence_id: int,
):
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
        phrase_id=phrase_id,
        song_id=song_id,
        start_occurrence_id=start_occurrence_id,
        end_occurrence_id=end_occurrence_id,
    )


def query_select_line_tokens_by_global_number(
    cursor,
    song_id: int,
    global_line_number: int,
):
    cursor.execute(
        """
        SELECT original_token
        FROM word_occurrences
        WHERE song_id = :song_id
          AND global_line_number = :global_line_number
        ORDER BY position_in_line
        """,
        song_id=song_id,
        global_line_number=global_line_number,
    )


def query_select_context_lines(
    cursor,
    song_id: int,
    previous_line: int,
    next_line: int,
):
    cursor.execute(
        """
        SELECT
            global_line_number,
            position_in_line,
            original_token
        FROM word_occurrences
        WHERE song_id = :song_id
          AND global_line_number BETWEEN :previous_line AND :next_line
        ORDER BY
            global_line_number,
            position_in_line
        """,
        song_id=song_id,
        previous_line=previous_line,
        next_line=next_line,
    )


# Songs


def query_insert_song_returning_id(
    cursor,
    title,
    artist,
    album,
    publication_year,
    upload_date,
    song_id,
):
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
        title=title,
        artist=artist,
        album=album,
        publication_year=publication_year,
        upload_date=upload_date,
        song_id=song_id,
    )


def query_insert_stanza_returning_id(cursor, song_id, stanza_number, stanza_id):
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
        song_id=song_id,
        stanza_number=stanza_number,
        stanza_id=stanza_id,
    )


def query_insert_word_occurrence(
    cursor,
    word_id,
    song_id,
    stanza_id,
    global_line_number,
    line_number_in_stanza,
    position_in_line,
    position_in_song,
    original_token,
):
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
        """,
        word_id=word_id,
        song_id=song_id,
        stanza_id=stanza_id,
        global_line_number=global_line_number,
        line_number_in_stanza=line_number_in_stanza,
        position_in_line=position_in_line,
        position_in_song=position_in_song,
        original_token=original_token,
    )


def query_select_song_text_rows(cursor, song_id):
    cursor.execute(
        """
        SELECT
            st.stanza_number,
            wo.global_line_number,
            wo.position_in_line,
            wo.original_token
        FROM word_occurrences wo
        JOIN stanzas st
            ON wo.stanza_id = st.stanza_id
        WHERE wo.song_id = :song_id
        ORDER BY
            st.stanza_number,
            wo.global_line_number,
            wo.position_in_line
        """,
        song_id=song_id,
    )


def query_count_matching_song(cursor, title, artist, album):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM songs
        WHERE LOWER(title) = LOWER(:title)
          AND LOWER(artist) = LOWER(:artist)
          AND (
                (album IS NULL AND :album IS NULL)
                OR LOWER(album) = LOWER(:album)
              )
        """,
        title=title,
        artist=artist,
        album=album,
    )


# Search


def query_search_songs(cursor, title=None, artist=None, album=None, publication_year=None):
    query = """
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
        WHERE 1 = 1
    """
    params = {}

    if title:
        query += " AND LOWER(title) LIKE LOWER(:title)"
        # the addition of % allow for LIKE comparison
        params["title"] = f"%{title}%"

    if artist:
        query += " AND LOWER(artist) LIKE LOWER(:artist)"
        # the addition of % allow for LIKE comparison
        params["artist"] = f"%{artist}%"

    if album:
        query += " AND LOWER(album) LIKE LOWER(:album)"
        # the addition of % allow for LIKE comparison
        params["album"] = f"%{album}%"

    if publication_year:
        query += " AND publication_year = :publication_year"
        params["publication_year"] = publication_year

    query += " ORDER BY title"

    cursor.execute(query, params)


def query_search_word_occurrences(cursor, word):
    cursor.execute(
        """
        SELECT
            wo.occurrence_id,
            s.song_id,
            s.title,
            s.artist,
            st.stanza_number,
            wo.global_line_number,
            wo.line_number_in_stanza,
            wo.position_in_line,
            wo.position_in_song,
            wo.original_token
        FROM words w
        JOIN word_occurrences wo
            ON w.word_id = wo.word_id
        JOIN songs s
            ON wo.song_id = s.song_id
        JOIN stanzas st
            ON wo.stanza_id = st.stanza_id
        WHERE w.text = LOWER(:word)
        ORDER BY
            s.song_id,
            wo.position_in_song
        """,
        word=word,
    )


def query_select_word_index(cursor, song_id: int | None = None, group_id: int | None = None) -> None:
    """Execute a word occurrence index query with optional song and group filters.

    Args:
        cursor: An open Oracle database cursor.
        song_id: Limit results to this song, or None for all songs.
        group_id: Limit results to words belonging to this group, or None for all groups.

    Returns:
        None. Query results remain available on the supplied cursor.
    """
    query = """
        SELECT
            w.text,
            s.song_id,
            s.title,
            st.stanza_number,
            wo.global_line_number,
            wo.line_number_in_stanza,
            wo.position_in_line
        FROM words w
        JOIN word_occurrences wo ON w.word_id = wo.word_id
        JOIN songs s ON wo.song_id = s.song_id
        JOIN stanzas st ON wo.stanza_id = st.stanza_id
        WHERE (:song_id IS NULL OR s.song_id = :song_id)
          AND (
              :group_id IS NULL
              OR EXISTS (
                  SELECT 1
                  FROM group_words gw
                  WHERE gw.group_id = :group_id
                    AND gw.word_id = w.word_id
              )
          )
        ORDER BY
            w.text,
            s.song_id,
            wo.position_in_song
    """
    cursor.execute(query, {"song_id": song_id, "group_id": group_id})


def query_select_line_tokens_by_stanza_position(
    cursor,
    song_id,
    stanza_number,
    line_number_in_stanza,
):
    cursor.execute(
        """
        SELECT wo.original_token
        FROM word_occurrences wo
        JOIN stanzas st
            ON wo.stanza_id = st.stanza_id
        WHERE wo.song_id = :song_id
          AND st.stanza_number = :stanza_number
          AND wo.line_number_in_stanza = :line_number_in_stanza
        ORDER BY wo.position_in_line
        """,
        song_id=song_id,
        stanza_number=stanza_number,
        line_number_in_stanza=line_number_in_stanza,
    )


def query_select_word_by_position(
    cursor,
    song_id,
    global_line_number,
    position_in_line,
):
    cursor.execute(
        """
        SELECT
            w.text,
            wo.original_token
        FROM word_occurrences wo
        JOIN words w
            ON wo.word_id = w.word_id
        WHERE wo.song_id = :song_id
          AND wo.global_line_number = :global_line_number
          AND wo.position_in_line = :position_in_line
        """,
        song_id=song_id,
        global_line_number=global_line_number,
        position_in_line=position_in_line,
    )


# Word groups


def query_select_group_id_by_name(cursor, group_name):
    cursor.execute(
        """
        SELECT group_id
        FROM word_groups
        WHERE LOWER(group_name) = LOWER(:group_name)
        """,
        group_name=group_name,
    )


def query_insert_group_returning_id(cursor, group_name, description, group_id):
    cursor.execute(
        """
        INSERT INTO word_groups (
            group_name,
            description
        )
        VALUES (
            :group_name,
            :description
        )
        RETURNING group_id INTO :group_id
        """,
        group_name=group_name,
        description=description,
        group_id=group_id,
    )


def query_delete_group_word_by_text(cursor, group_id, word):
    cursor.execute(
        """
        DELETE FROM group_words
        WHERE group_id = :group_id
          AND word_id = (
                SELECT word_id
                FROM words
                WHERE text = :word
          )
        """,
        group_id=group_id,
        word=word,
    )


def query_select_group_words(cursor, group_id):
    cursor.execute(
        """
        SELECT
            w.word_id,
            w.text
        FROM group_words gw
        JOIN words w
            ON gw.word_id = w.word_id
        WHERE gw.group_id = :group_id
        ORDER BY w.text
        """,
        group_id=group_id,
    )


def query_select_groups(cursor):
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
        ORDER BY group_name
        """
    )


def query_select_group_occurrences(cursor, group_id):
    cursor.execute(
        """
        SELECT
            w.text,
            s.song_id,
            s.title,
            st.stanza_number,
            wo.global_line_number,
            wo.line_number_in_stanza,
            wo.position_in_line,
            wo.original_token
        FROM group_words gw
        JOIN words w
            ON gw.word_id = w.word_id
        JOIN word_occurrences wo
            ON w.word_id = wo.word_id
        JOIN songs s
            ON wo.song_id = s.song_id
        JOIN stanzas st
            ON wo.stanza_id = st.stanza_id
        WHERE gw.group_id = :group_id
        ORDER BY
            w.text,
            s.song_id,
            wo.position_in_song
        """,
        group_id=group_id,
    )


def query_update_group(cursor, group_id, group_name, description):
    cursor.execute(
        """
        UPDATE word_groups
        SET
            group_name = :group_name,
            description = :description
        WHERE group_id = :group_id
        """,
        group_name=group_name,
        description=description,
        group_id=group_id,
    )


def query_delete_group(cursor, group_id):
    cursor.execute(
        """
        DELETE FROM word_groups
        WHERE group_id = :group_id
        """,
        group_id=group_id,
    )


# Phrases


def query_insert_phrase_returning_id(cursor, phrase_name, phrase_text, phrase_id):
    cursor.execute(
        """
        INSERT INTO phrases (
            phrase_name,
            phrase_text
        )
        VALUES (
            :phrase_name,
            :phrase_text
        )
        RETURNING phrase_id INTO :phrase_id
        """,
        phrase_name=phrase_name,
        phrase_text=phrase_text,
        phrase_id=phrase_id,
    )


def query_select_phrase_search_occurrences(cursor):
    cursor.execute(
        """
        SELECT
            wo.occurrence_id,
            wo.song_id,
            wo.global_line_number,
            wo.position_in_line,
            w.text
        FROM word_occurrences wo
        JOIN words w
            ON wo.word_id = w.word_id
        ORDER BY
            wo.song_id,
            wo.global_line_number,
            wo.position_in_line
        """
    )


def query_select_song_word_occurrences_for_phrases(
    cursor: oracledb.Cursor,
    song_id: int,
) -> None:
    """Select normalized words and locations from one song for phrase matching."""
    logger.debug(f"Loading occurrences for phrase matching in song {song_id}")
    cursor.execute(
        """
        SELECT
            wo.occurrence_id,
            wo.song_id,
            wo.global_line_number,
            wo.position_in_line,
            w.text
        FROM word_occurrences wo
        JOIN words w ON w.word_id = wo.word_id
        WHERE wo.song_id = :song_id
        ORDER BY wo.global_line_number, wo.position_in_line
        """,
        song_id=song_id,
    )


def query_delete_phrase_occurrences(cursor, phrase_id):
    cursor.execute(
        """
        DELETE FROM phrase_occurrences
        WHERE phrase_id = :phrase_id
        """,
        phrase_id=phrase_id,
    )


def query_select_phrases(cursor):
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
        ORDER BY phrase_name
        """
    )


def query_delete_phrase(cursor, phrase_id):
    cursor.execute(
        """
        DELETE FROM phrases
        WHERE phrase_id = :phrase_id
        """,
        phrase_id=phrase_id,
    )


def query_select_phrase_occurrences(cursor, phrase_id):
    cursor.execute(
        """
        SELECT
            s.song_id,
            s.title,
            start_occ.global_line_number,
            start_occ.position_in_line,
            end_occ.position_in_line
        FROM phrase_occurrences po
        JOIN songs s
            ON po.song_id = s.song_id
        JOIN word_occurrences start_occ
            ON po.start_occurrence_id = start_occ.occurrence_id
        JOIN word_occurrences end_occ
            ON po.end_occurrence_id = end_occ.occurrence_id
        WHERE po.phrase_id = :phrase_id
        ORDER BY
            s.song_id,
            start_occ.position_in_song
        """,
        phrase_id=phrase_id,
    )


# Statistics


def query_select_database_summary(cursor):
    cursor.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM songs) AS song_count,
            (
                SELECT COUNT(*)
                FROM word_occurrences
            ) AS total_words,
            (
                SELECT COUNT(*)
                FROM words
            ) AS unique_words,
            (
                SELECT ROUND(
                    AVG(LENGTH(w.text)),
                    2
                )
                FROM word_occurrences wo
                JOIN words w
                    ON wo.word_id = w.word_id
            ) AS average_word_length,
            (
                SELECT ROUND(
                    AVG(words_per_line),
                    2
                )
                FROM (
                    SELECT
                        COUNT(*) AS words_per_line
                    FROM word_occurrences
                    GROUP BY
                        song_id,
                        global_line_number
                )
            ) AS average_words_per_line
        FROM dual
        """
    )


def query_select_song_statistics(cursor, song_id):
    cursor.execute(
        """
        SELECT
            s.title,
            COUNT(
                DISTINCT wo.stanza_id
            ) AS stanza_count,
            COUNT(
                DISTINCT wo.global_line_number
            ) AS line_count,
            COUNT(
                wo.occurrence_id
            ) AS word_count,
            COUNT(
                DISTINCT wo.word_id
            ) AS unique_word_count,
            ROUND(
                AVG(LENGTH(w.text)),
                2
            ) AS average_word_length
        FROM songs s
        LEFT JOIN word_occurrences wo
            ON s.song_id = wo.song_id
        LEFT JOIN words w
            ON wo.word_id = w.word_id
        WHERE s.song_id = :song_id
        GROUP BY
            s.song_id,
            s.title
        """,
        song_id=song_id,
    )


def query_select_words_by_frequency(cursor, limit, song_id=None, descending=True):
    order_direction = "DESC" if descending else "ASC"
    query = f"""
        SELECT
            word_text,
            occurrence_count
        FROM (
            SELECT
                w.text AS word_text,
                COUNT(*) AS occurrence_count
            FROM words w
            JOIN word_occurrences wo
                ON w.word_id = wo.word_id
    """
    params = {"limit": limit}

    if song_id is not None:
        query += " WHERE wo.song_id = :song_id"
        params["song_id"] = song_id

    query += f"""
            GROUP BY w.text
            ORDER BY
                occurrence_count {order_direction},
                w.text
        )
        WHERE ROWNUM <= :limit
    """

    cursor.execute(query, params)


def query_select_word_length_distribution(cursor, song_id=None):
    query = """
        SELECT
            LENGTH(w.text) AS word_length,
            COUNT(*) AS occurrence_count
        FROM words w
        JOIN word_occurrences wo
            ON w.word_id = wo.word_id
    """
    params = {}

    if song_id is not None:
        query += " WHERE wo.song_id = :song_id"
        params["song_id"] = song_id

    query += """
        GROUP BY
            LENGTH(w.text)
        ORDER BY
            LENGTH(w.text)
    """

    cursor.execute(query, params)


def query_select_words_per_stanza(cursor, song_id):
    cursor.execute(
        """
        SELECT
            st.stanza_number,
            COUNT(
                wo.occurrence_id
            ) AS word_count
        FROM stanzas st
        LEFT JOIN word_occurrences wo
            ON st.stanza_id = wo.stanza_id
        WHERE st.song_id = :song_id
        GROUP BY
            st.stanza_id,
            st.stanza_number
        ORDER BY
            st.stanza_number
        """,
        song_id=song_id,
    )


# XML backup and restore


def query_select_songs_for_xml_export(cursor):
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


def query_select_stanzas_for_xml_export(cursor):
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


def query_select_words_for_xml_export(cursor):
    cursor.execute(
        """
        SELECT
            word_id,
            text
        FROM words
        ORDER BY word_id
        """
    )


def query_select_word_occurrences_for_xml_export(cursor):
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


def query_select_word_groups_for_xml_export(cursor):
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


def query_select_group_words_for_xml_export(cursor):
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


def query_select_phrases_for_xml_export(cursor):
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


def query_select_phrase_occurrences_for_xml_export(cursor):
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


def query_delete_table_data(cursor, table_name):
    cursor.execute(
        f"DELETE FROM {table_name}"
    )


def query_insert_word_occurrence_for_xml_restore(
    cursor,
    word_id,
    song_id,
    stanza_id,
    global_line_number,
    line_number_in_stanza,
    position_in_line,
    position_in_song,
    original_token,
    occurrence_id,
):
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
        word_id=word_id,
        song_id=song_id,
        stanza_id=stanza_id,
        global_line_number=global_line_number,
        line_number_in_stanza=line_number_in_stanza,
        position_in_line=position_in_line,
        position_in_song=position_in_song,
        original_token=original_token,
        occurrence_id=occurrence_id,
    )


def query_insert_word_group_for_xml_restore(
    cursor,
    group_name,
    description,
    creation_date,
    group_id,
):
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
        group_name=group_name,
        description=description,
        creation_date=creation_date,
        group_id=group_id,
    )


def query_insert_phrase_for_xml_restore(
    cursor,
    phrase_name,
    phrase_text,
    creation_date,
    phrase_id,
):
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
        phrase_name=phrase_name,
        phrase_text=phrase_text,
        creation_date=creation_date,
        phrase_id=phrase_id,
    )


def query_select_uploaded_song_summary(cursor: oracledb.Cursor, song_id: int) -> None:
    """'
    Select persisted stanza, line and word counts for a single song.
    """
    logger.info(f"Selecting upload summary for song id {song_id}")
    cursor.execute(
        """
        SELECT COUNT(DISTINCT stanza_id) AS stanza_count,
               COUNT(DISTINCT global_line_number) AS line_count,
               COUNT(*) AS word_count
        FROM word_occurrences
        WHERE song_id = :song_id
        """,
        song_id=song_id,
    )


def query_select_all_songs_with_counts(cursor: oracledb.Cursor) -> None:
    """Select each song and its persisted stanza, line and word counts.

    Args:
        cursor: Open Oracle cursor managed by the calling service.

    Returns:
        None. The caller fetches the result set from cursor.
    """
    logger.info("Selecting all songs with their stanza, line and word counts")
    cursor.execute(
        """
        SELECT
            s.song_id,
            s.title,
            s.artist,
            s.album,
            s.publication_year,
            COUNT(DISTINCT wo.stanza_id) AS stanza_count,
            COUNT(DISTINCT wo.global_line_number) AS line_count,
            COUNT(wo.occurrence_id) AS word_count
        FROM songs s
        LEFT JOIN word_occurrences wo ON wo.song_id = s.song_id
        GROUP BY
            s.song_id,
            s.title,
            s.artist,
            s.album,
            s.publication_year
        ORDER BY LOWER(s.title), LOWER(s.artist), s.song_id
        """
    )
