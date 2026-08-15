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
