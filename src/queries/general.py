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
