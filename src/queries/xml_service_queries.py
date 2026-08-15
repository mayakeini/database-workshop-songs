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
