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


def query_select_word_index(cursor, song_id=None):
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
        JOIN word_occurrences wo
            ON w.word_id = wo.word_id
        JOIN songs s
            ON wo.song_id = s.song_id
        JOIN stanzas st
            ON wo.stanza_id = st.stanza_id
    """
    params = {}

    if song_id is not None:
        query += " WHERE s.song_id = :song_id"
        params["song_id"] = song_id

    query += """
        ORDER BY
            w.text,
            s.song_id,
            wo.position_in_song
    """

    cursor.execute(query, params)


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
