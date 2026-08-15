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
