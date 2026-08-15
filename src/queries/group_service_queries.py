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
