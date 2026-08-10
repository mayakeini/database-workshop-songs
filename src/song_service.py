import logging

from datetime import datetime
from zoneinfo import ZoneInfo

from src.db import get_connection
from src.text_parser import parse_song

logger = logging.getLogger(__name__)


def insert_song(
    file_path: str,
    title: str,
    artist: str,
    album: str | None,
    publication_year: int,
) -> int:
    """
    Parses a song file and inserts the song, stanzas, words,
    and word occurrences into the database.

    Args:
        file_path: Path to the TXT song file.
        title: Song title.
        artist: Artist name.
        album: Optional album name.
        publication_year: Year the song was published.

    Returns:
        The database ID of the inserted song.

    Raises:
        Exception: If parsing or database insertion fails.
    """
    logger.info(fr"Starting song insertion: {title}")

    if song_exists(
            title=title,
            artist=artist,
            album=album,
    ):
        logger.warning(
            "Song insertion rejected because it already exists: '%s' by '%s'",
            title,
            artist,
        )
        raise ValueError(
            f"The song '{title}' by '{artist}' already exists."
        )

    occurrences = parse_song(file_path)

    if not occurrences:
        logger.warning(
            "Song upload rejected because the file contains no valid words: %s",
            file_path,
        )

        raise ValueError(
            "The uploaded song file is empty or contains no valid words."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        song_id_var = cursor.var(int)

        israel_time = datetime.now(
            ZoneInfo("Asia/Jerusalem")
        )

        logger.info(
            "Using Israel upload time: %s",
            israel_time,
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
            title=title,
            artist=artist,
            album=album,
            publication_year=publication_year,
            upload_date=israel_time,
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

def song_exists(
    title: str,
    artist: str,
    album: str | None,
) -> bool:
    """
    Checks whether a song with the same title, artist, and album
    already exists in the database.

    Args:
        title: Song title.
        artist: Artist name.
        album: Album name, or None if no album was provided.

    Returns:
        True if a matching song already exists, otherwise False.

    Raises:
        Exception: If the database query fails.
    """
    logger.info(
        "Checking whether song already exists: title='%s', artist='%s', album='%s'",
        title,
        artist,
        album,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

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

        count = cursor.fetchone()[0]
        exists = count > 0

        logger.info(
            "Song existence check completed. Exists=%s",
            exists,
        )

        return exists

    except Exception:
        logger.exception(
            "Failed to check whether song '%s' already exists",
            title,
        )
        raise

    finally:
        connection.close()