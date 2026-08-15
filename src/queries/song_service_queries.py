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
