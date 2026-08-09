import logging

from src.db import get_connection
from src.text_parser import parse_song

logger = logging.getLogger(__name__)


def insert_song(file_path: str, title: str, artist: str, album: str, publication_year: int) -> int:
    """
    Insert song into Oracle
    :param file_path: str of the file path
    :param title: str of the title
    :param artist: str of the artist name
    :param album: str of the album name
    :param publication_year: int of the publication year
    :return: song id
    """
    logger.info(fr"Starting song insertion: {title}")

    occurrences = parse_song(file_path)

    connection = get_connection()

    try:
        cursor = connection.cursor()

        song_id_var = cursor.var(int)

        cursor.execute(
            """
            INSERT INTO songs (
                title,
                artist,
                album,
                publication_year
            )
            VALUES (
                :title,
                :artist,
                :album,
                :publication_year
            )
            RETURNING song_id INTO :song_id
            """,
            title=title,
            artist=artist,
            album=album,
            publication_year=publication_year,
            song_id=song_id_var,
        )

        song_id = song_id_var.getvalue()[0]

        logger.info("Inserted song with id %s", song_id)

        stanza_ids = {}

        for occurrence in occurrences:
            stanza_number = occurrence["stanza_number"]

            if stanza_number not in stanza_ids:
                stanza_id_var = cursor.var(int)

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
                    stanza_id=stanza_id_var,
                )

                stanza_ids[stanza_number] = stanza_id_var.getvalue()[0]

        word_ids = {}

        for occurrence in occurrences:
            word = occurrence["normalized_word"]

            if word not in word_ids:
                cursor.execute(
                    """
                    SELECT word_id
                    FROM words
                    WHERE text = :word
                    """,
                    word=word,
                )

                row = cursor.fetchone()

                if row:
                    word_id = row[0]

                else:
                    word_id_var = cursor.var(int)

                    cursor.execute(
                        """
                        INSERT INTO words (
                            text,
                            word_length
                        )
                        VALUES (
                            :word,
                            :word_length
                        )
                        RETURNING word_id INTO :word_id
                        """,
                        word=word,
                        word_length=len(word),
                        word_id=word_id_var,
                    )

                    word_id = word_id_var.getvalue()[0]

                word_ids[word] = word_id

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
                word_id=word_ids[word],
                song_id=song_id,
                stanza_id=stanza_ids[occurrence["stanza_number"]],
                global_line_number=occurrence["global_line_number"],
                line_number_in_stanza=occurrence["line_number_in_stanza"],
                position_in_line=occurrence["position_in_line"],
                position_in_song=occurrence["position_in_song"],
                original_token=occurrence["original_token"],
            )

        connection.commit()

        logger.info(
            "Song inserted successfully: %s (%s occurrences)",
            title,
            len(occurrences),
        )

        return song_id

    except Exception:
        connection.rollback()
        logger.exception("Failed to insert song: %s", title)
        raise

    finally:
        connection.close()


def get_line(song_id: int, global_line_number: int) -> str:
    """
    Get a song line by song id and line number
    :param song_id: int of the song id
    :param global_line_number: int of the global line number
    :return: str of the song line
    """
    logger.info(fr"Get the song line of song id {song_id}, line number {global_line_number}")
    connection = get_connection()

    try:
        cursor = connection.cursor()

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

        tokens = [row[0] for row in cursor.fetchall()]

        return " ".join(tokens)

    finally:
        connection.close()


def get_song_text(song_id: int) -> str:
    """
    Get a song text by song id
    :param song_id: int of the song id
    :return: str of the song text
    """
    logger.info(fr"Get the song text of song id {song_id}")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                s.stanza_number,
                wo.global_line_number,
                wo.position_in_line,
                wo.original_token
            FROM word_occurrences wo
            JOIN stanzas s
                ON wo.stanza_id = s.stanza_id
            WHERE wo.song_id = :song_id
            ORDER BY
                s.stanza_number,
                wo.global_line_number,
                wo.position_in_line
            """,
            song_id=song_id,
        )

        rows = cursor.fetchall()

        if not rows:
            return ""

        result = []

        current_stanza = None
        current_line = None
        line_tokens = []

        for stanza_number, line_number, position, token in rows:

            if current_stanza is not None and stanza_number != current_stanza:
                if line_tokens:
                    result.append(" ".join(line_tokens))
                    line_tokens = []

                result.append("")

            elif current_line is not None and line_number != current_line:
                result.append(" ".join(line_tokens))
                line_tokens = []

            line_tokens.append(token)

            current_stanza = stanza_number
            current_line = line_number

        if line_tokens:
            result.append(" ".join(line_tokens))

        return "\n".join(result)

    finally:
        connection.close()