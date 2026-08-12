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
        ValueError: If the song already exists, the file contains no
            valid words, or the publication year is invalid.
        Exception: If parsing or database insertion fails.
    """
    title = title.strip()
    artist = artist.strip()
    album = album.strip() if album and album.strip() else None

    logger.info(
        "Starting song insertion: '%s' by '%s'",
        title,
        artist,
    )

    current_year = datetime.now(
        ZoneInfo("Asia/Jerusalem")
    ).year

    if publication_year < 1000 or publication_year > current_year:
        logger.warning(
            "Song insertion rejected due to invalid "
            "publication year: %s",
            publication_year,
        )

        raise ValueError(
            f"Publication year must be between 1000 "
            f"and {current_year}."
        )

    if song_exists(
        title=title,
        artist=artist,
        album=album,
    ):
        logger.warning(
            "Song insertion rejected because it already exists: "
            "'%s' by '%s'",
            title,
            artist,
        )

        raise ValueError(
            f"The song '{title}' by '{artist}' already exists."
        )

    occurrences = parse_song(
        file_path
    )

    if not occurrences:
        logger.warning(
            "Song upload rejected because the file "
            "contains no valid words: %s",
            file_path,
        )

        raise ValueError(
            "The uploaded song file is empty "
            "or contains no valid words."
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

        logger.info(
            "Inserted song with id %s",
            song_id,
        )

        stanza_ids: dict[int, int] = {}

        for occurrence in occurrences:
            stanza_number = occurrence[
                "stanza_number"
            ]

            if stanza_number in stanza_ids:
                continue

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

            stanza_id = stanza_id_var.getvalue()[0]

            stanza_ids[
                stanza_number
            ] = stanza_id

            logger.debug(
                "Inserted stanza %s with id %s "
                "for song id %s",
                stanza_number,
                stanza_id,
                song_id,
            )

        word_ids: dict[str, int] = {}

        for occurrence in occurrences:
            word = occurrence[
                "normalized_word"
            ]

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

                if row is not None:
                    word_id = row[0]

                    logger.debug(
                        "Using existing word '%s' "
                        "with id %s",
                        word,
                        word_id,
                    )

                else:
                    word_id_var = cursor.var(int)

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
                        word_id=word_id_var,
                    )

                    word_id = word_id_var.getvalue()[0]

                    logger.debug(
                        "Inserted new word '%s' "
                        "with id %s",
                        word,
                        word_id,
                    )

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
                stanza_id=stanza_ids[
                    occurrence["stanza_number"]
                ],
                global_line_number=occurrence[
                    "global_line_number"
                ],
                line_number_in_stanza=occurrence[
                    "line_number_in_stanza"
                ],
                position_in_line=occurrence[
                    "position_in_line"
                ],
                position_in_song=occurrence[
                    "position_in_song"
                ],
                original_token=occurrence[
                    "original_token"
                ],
            )

        connection.commit()

        logger.info(
            "Song inserted successfully: '%s' "
            "(%s occurrences)",
            title,
            len(occurrences),
        )

        return song_id

    except Exception:
        connection.rollback()

        logger.exception(
            "Failed to insert song: '%s'",
            title,
        )

        raise

    finally:
        connection.close()


def get_line(
    song_id: int,
    global_line_number: int,
) -> str:
    """
    Reconstructs a specific line of a song.

    Args:
        song_id: The database ID of the song.
        global_line_number: The global line number in the song.

    Returns:
        The reconstructed song line. Returns an empty string if
        the requested line does not exist.

    Raises:
        Exception: If the database query fails.
    """
    logger.info(
        "Fetching line %s for song id %s",
        global_line_number,
        song_id,
    )

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

        tokens = [
            row[0]
            for row in cursor.fetchall()
        ]

        line = " ".join(tokens)

        logger.info(
            "Line %s for song id %s reconstructed successfully",
            global_line_number,
            song_id,
        )

        return line

    except Exception:
        logger.exception(
            "Failed to fetch line %s for song id %s",
            global_line_number,
            song_id,
        )
        raise

    finally:
        connection.close()


def get_song_text(
    song_id: int,
) -> str:
    """
    Reconstructs the complete text of a song from its word occurrences.

    Blank lines are inserted between stanzas.

    Args:
        song_id: The database ID of the song.

    Returns:
        The reconstructed song text. Returns an empty string if
        the song has no word occurrences.

    Raises:
        Exception: If the database query fails.
    """
    logger.info(
        "Fetching complete text for song id %s",
        song_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

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

        rows = cursor.fetchall()

        if not rows:
            logger.info(
                "No text found for song id %s",
                song_id,
            )
            return ""

        result: list[str] = []

        current_stanza: int | None = None
        current_line: int | None = None
        line_tokens: list[str] = []

        for (
            stanza_number,
            line_number,
            position,
            token,
        ) in rows:
            if (
                current_stanza is not None
                and stanza_number != current_stanza
            ):
                if line_tokens:
                    result.append(
                        " ".join(line_tokens)
                    )
                    line_tokens = []

                result.append("")

            elif (
                current_line is not None
                and line_number != current_line
            ):
                result.append(
                    " ".join(line_tokens)
                )
                line_tokens = []

            line_tokens.append(
                token
            )

            current_stanza = stanza_number
            current_line = line_number

        if line_tokens:
            result.append(
                " ".join(line_tokens)
            )

        song_text = "\n".join(
            result
        )

        logger.info(
            "Complete text for song id %s "
            "reconstructed successfully",
            song_id,
        )

        return song_text

    except Exception:
        logger.exception(
            "Failed to reconstruct text for song id %s",
            song_id,
        )
        raise

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

    The comparison is case-insensitive.

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
        "Checking whether song already exists: "
        "title='%s', artist='%s', album='%s'",
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