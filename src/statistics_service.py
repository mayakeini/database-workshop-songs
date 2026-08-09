import logging
from typing import Optional

from src.db import get_connection

logger = logging.getLogger(__name__)


def get_database_summary() -> dict[str, int | float]:
    """
    Returns general statistics for the entire database.

    The statistics include:
    - Number of songs.
    - Total number of word occurrences.
    - Number of unique words.
    - Average word length across all word occurrences.
    - Average number of words per line.

    Returns:
        A dictionary containing the calculated statistics.

    Raises:
        Exception: If the database query fails.
    """
    logger.info("Fetching database summary statistics")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM songs) AS song_count,
                (SELECT COUNT(*) FROM word_occurrences) AS total_words,
                (SELECT COUNT(*) FROM words) AS unique_words,
                (
                    SELECT ROUND(AVG(w.word_length), 2)
                    FROM word_occurrences wo
                    JOIN words w
                        ON wo.word_id = w.word_id
                ) AS average_word_length,
                (
                    SELECT ROUND(AVG(words_per_line), 2)
                    FROM (
                        SELECT COUNT(*) AS words_per_line
                        FROM word_occurrences
                        GROUP BY song_id, global_line_number
                    )
                ) AS average_words_per_line
            FROM dual
            """
        )

        row = cursor.fetchone()

        result = {
            "song_count": row[0],
            "total_words": row[1],
            "unique_words": row[2],
            "average_word_length": row[3] or 0,
            "average_words_per_line": row[4] or 0,
        }

        logger.info(
            "Database summary fetched successfully: %s",
            result,
        )

        return result

    except Exception:
        logger.exception("Failed to fetch database summary")
        raise

    finally:
        connection.close()


def get_song_statistics(song_id: int) -> Optional[dict[str, int | float | str]]:
    """
    Returns statistics for a specific song.

    Args:
        song_id: The database ID of the song.

    Returns:
        A dictionary containing the song statistics, or None if the
        song does not exist.

    Raises:
        Exception: If the database query fails.
    """
    logger.info(
        "Fetching statistics for song id %s",
        song_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                s.title,
                COUNT(DISTINCT wo.stanza_id) AS stanza_count,
                COUNT(DISTINCT wo.global_line_number) AS line_count,
                COUNT(wo.occurrence_id) AS word_count,
                COUNT(DISTINCT wo.word_id) AS unique_word_count,
                ROUND(AVG(w.word_length), 2) AS average_word_length
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

        row = cursor.fetchone()

        if row is None:
            logger.warning(
                "Song id %s was not found",
                song_id,
            )
            return None

        result = {
            "title": row[0],
            "stanza_count": row[1],
            "line_count": row[2],
            "word_count": row[3],
            "unique_word_count": row[4],
            "average_word_length": row[5] or 0,
        }

        logger.info(
            "Statistics for song id %s fetched successfully",
            song_id,
        )

        return result

    except Exception:
        logger.exception(
            "Failed to fetch statistics for song id %s",
            song_id,
        )
        raise

    finally:
        connection.close()


def get_most_frequent_words(
    limit: int = 10,
    song_id: Optional[int] = None,
) -> list[tuple[str, int]]:
    """
    Returns the most frequently occurring words.

    Args:
        limit: Maximum number of words to return.
        song_id: Optional song ID. If provided, statistics are
            calculated only for that song.

    Returns:
        A list of tuples in the format:
        [
            (word, occurrence_count),
            ...
        ]

    Raises:
        ValueError: If limit is not positive.
        Exception: If the database query fails.
    """
    if limit <= 0:
        logger.warning(
            "Invalid frequency result limit: %s",
            limit,
        )
        raise ValueError("Limit must be greater than zero")

    logger.info(
        "Fetching %s most frequent words%s",
        limit,
        f" for song id {song_id}" if song_id is not None else "",
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        if song_id is None:
            cursor.execute(
                """
                SELECT word_text, occurrence_count
                FROM (
                    SELECT
                        w.text AS word_text,
                        COUNT(*) AS occurrence_count
                    FROM words w
                    JOIN word_occurrences wo
                        ON w.word_id = wo.word_id
                    GROUP BY w.text
                    ORDER BY
                        occurrence_count DESC,
                        w.text
                )
                WHERE ROWNUM <= :limit
                """,
                limit=limit,
            )

        else:
            cursor.execute(
                """
                SELECT word_text, occurrence_count
                FROM (
                    SELECT
                        w.text AS word_text,
                        COUNT(*) AS occurrence_count
                    FROM words w
                    JOIN word_occurrences wo
                        ON w.word_id = wo.word_id
                    WHERE wo.song_id = :song_id
                    GROUP BY w.text
                    ORDER BY
                        occurrence_count DESC,
                        w.text
                )
                WHERE ROWNUM <= :limit
                """,
                song_id=song_id,
                limit=limit,
            )

        result = cursor.fetchall()

        logger.info(
            "Fetched %s frequent words",
            len(result),
        )

        return result

    except Exception:
        logger.exception("Failed to fetch most frequent words")
        raise

    finally:
        connection.close()


def get_rarest_words(
    limit: int = 10,
    song_id: Optional[int] = None,
) -> list[tuple[str, int]]:
    """
    Returns the least frequently occurring words.

    Args:
        limit: Maximum number of words to return.
        song_id: Optional song ID. If provided, statistics are
            calculated only for that song.

    Returns:
        A list of tuples containing:
        (
            word,
            occurrence_count
        )

    Raises:
        ValueError: If limit is not positive.
        Exception: If the database query fails.
    """
    if limit <= 0:
        logger.warning(
            "Invalid rare-word result limit: %s",
            limit,
        )
        raise ValueError("Limit must be greater than zero")

    logger.info(
        "Fetching %s rarest words%s",
        limit,
        f" for song id {song_id}" if song_id is not None else "",
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        if song_id is None:
            cursor.execute(
                """
                SELECT word_text, occurrence_count
                FROM (
                    SELECT
                        w.text AS word_text,
                        COUNT(*) AS occurrence_count
                    FROM words w
                    JOIN word_occurrences wo
                        ON w.word_id = wo.word_id
                    GROUP BY w.text
                    ORDER BY
                        occurrence_count ASC,
                        w.text
                )
                WHERE ROWNUM <= :limit
                """,
                limit=limit,
            )

        else:
            cursor.execute(
                """
                SELECT word_text, occurrence_count
                FROM (
                    SELECT
                        w.text AS word_text,
                        COUNT(*) AS occurrence_count
                    FROM words w
                    JOIN word_occurrences wo
                        ON w.word_id = wo.word_id
                    WHERE wo.song_id = :song_id
                    GROUP BY w.text
                    ORDER BY
                        occurrence_count ASC,
                        w.text
                )
                WHERE ROWNUM <= :limit
                """,
                song_id=song_id,
                limit=limit,
            )

        result = cursor.fetchall()

        logger.info(
            "Fetched %s rare words",
            len(result),
        )

        return result

    except Exception:
        logger.exception("Failed to fetch rarest words")
        raise

    finally:
        connection.close()


def get_word_length_distribution(
    song_id: Optional[int] = None,
) -> list[tuple[int, int]]:
    """
    Returns the distribution of word lengths.

    Args:
        song_id: Optional song ID. If provided, the distribution is
            calculated only for that song.

    Returns:
        A list of tuples in the format:
        [
            (word_length, occurrence_count),
            ...
        ]

    Raises:
        Exception: If the database query fails.
    """
    logger.info(
        "Fetching word length distribution%s",
        f" for song id {song_id}" if song_id is not None else "",
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        if song_id is None:
            cursor.execute(
                """
                SELECT
                    w.word_length,
                    COUNT(*) AS occurrence_count
                FROM words w
                JOIN word_occurrences wo
                    ON w.word_id = wo.word_id
                GROUP BY w.word_length
                ORDER BY w.word_length
                """
            )

        else:
            cursor.execute(
                """
                SELECT
                    w.word_length,
                    COUNT(*) AS occurrence_count
                FROM words w
                JOIN word_occurrences wo
                    ON w.word_id = wo.word_id
                WHERE wo.song_id = :song_id
                GROUP BY w.word_length
                ORDER BY w.word_length
                """,
                song_id=song_id,
            )

        result = cursor.fetchall()

        logger.info(
            "Fetched word length distribution with %s different lengths",
            len(result),
        )

        return result

    except Exception:
        logger.exception(
            "Failed to fetch word length distribution"
        )
        raise

    finally:
        connection.close()


def get_words_per_stanza(
    song_id: int,
) -> list[tuple[int, int]]:
    """
    Returns the number of words in each stanza of a song.

    Args:
        song_id: The database ID of the song.

    Returns:
        A list of tuples in the format:
        [
            (stanza_number, word_count),
            ...
        ]

    Raises:
        Exception: If the database query fails.
    """
    logger.info(
        "Fetching word count per stanza for song id %s",
        song_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                st.stanza_number,
                COUNT(wo.occurrence_id) AS word_count
            FROM stanzas st
            LEFT JOIN word_occurrences wo
                ON st.stanza_id = wo.stanza_id
            WHERE st.song_id = :song_id
            GROUP BY
                st.stanza_id,
                st.stanza_number
            ORDER BY st.stanza_number
            """,
            song_id=song_id,
        )

        result = cursor.fetchall()

        logger.info(
            "Fetched statistics for %s stanzas in song id %s",
            len(result),
            song_id,
        )

        return result

    except Exception:
        logger.exception(
            "Failed to fetch word count per stanza for song id %s",
            song_id,
        )
        raise

    finally:
        connection.close()