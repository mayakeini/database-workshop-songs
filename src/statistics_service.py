import logging
from typing import Optional

from src.db import get_database_service
from src.queries.db_queries import query_select_database_summary, query_select_song_statistics,
    query_select_word_length_distribution, query_select_words_by_frequency, query_select_words_per_stanza

logger = logging.getLogger(__name__)


def get_database_summary() -> dict:
    """
    Returns general statistics for the entire database.
    :return: A dictionary containing the calculated statistics.
    """
    logger.info("Fetching database summary statistics")

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_database_summary(cursor)
            row = cursor.fetchone()
            result = {
                "song_count": row[0],
                "total_words": row[1],
                "unique_words": row[2],
                "average_word_length": row[3] or 0,
                "average_words_per_line": row[4] or 0
            }

            logger.info(f'Database summary fetched successfully: {result}')
            return result

    except Exception as e:
        logger.error(f"Failed to fetch database summary due to {e}")
        raise


def get_song_statistics(song_id: int) -> dict:
    """
    Returns statistics for a specific song.
    Word length is calculated dynamically using the WORDS.text column and is not stored separately in the database.
    :param song_id: The database ID of the song.
    :return: A dictionary containing the song statistics, or None if the song does not exist.
    """
    logger.info(f'Fetching statistics for song id {song_id}')

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_song_statistics(cursor, song_id)
            row = cursor.fetchone()

            if row is None:
                logger.warning(f'Song id {song_id} was not found')
                return None

            result = {
                "title": row[0],
                "stanza_count": row[1],
                "line_count": row[2],
                "word_count": row[3],
                "unique_word_count": row[4],
                "average_word_length": row[5] or 0
            }

            logger.info(f'Statistics for song id {song_id} fetched successfully')
            return result

    except Exception as e:
        logger.error(f'Failed to fetch statistics for song id {song_id} due to {e}')
        raise


def get_most_frequent_words(limit: int = 10, song_id: Optional[int] = None) -> list[tuple[str, int]]:
    """
    Returns the most frequently occurring words.
    :param limit: Maximum number of words to return.
    :param song_id: Optional song ID. If provided, statistics are calculated only for that song.
    :return: A list of tuples in the format: [(word, occurrence_count), ...]
    """
    if limit < 1:
        logger.warning(f'Invalid frequency result limit: {limit} - set limit to 1')
        limit = 1

    logger.info(f"Fetching {limit} most frequent words{f' for song id {song_id}' if song_id is not None else ''}")

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_words_by_frequency(
                cursor,
                limit=limit,
                song_id=song_id,
                descending=True
            )

            result = cursor.fetchall()
            logger.info(f'Fetched {len(result)} frequent words')
            return result

    except Exception as e:
        logger.error(f"Failed to fetch most frequent words due to {e}")
        raise


def get_rarest_words(limit: int = 10, song_id: Optional[int] = None) -> list[tuple[str, int]]:
    """
    Returns the least frequently occurring words.
    :param limit: Maximum number of words to return.
    :param song_id: Optional song ID. If provided, statistics are calculated only for that song.
    :return: A list of tuples in the format: [(word, occurrence_count), ...]
    """
    if limit < 1:
        logger.warning(f'Invalid rare-word result limit: {limit} - set limit to 1')
        limit = 1

    logger.info(f"Fetching {limit} rarest words{f' for song id {song_id}' if song_id is not None else ''}")

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_words_by_frequency(
                cursor,
                limit=limit,
                song_id=song_id,
                descending=False
            )

            result = cursor.fetchall()
            logger.info(f'Fetched {len(result)} rare words')
            return result

    except Exception as e:
        logger.error(f"Failed to fetch rarest words due to {e}")
        raise


def get_word_length_distribution(song_id: int = None) -> list:
    """
    Returns the distribution of word lengths.
    Word length is calculated dynamically using LENGTH(words.text).
    :param song_id: Optional song ID. If provided, the distribution is calculated only for that song.
    :return: A list of tuples in the format: [(word_length, occurrence_count), ...]
    """
    logger.info(f"Fetching word length distribution{f' for song id {song_id}' if song_id is not None else ''}")

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_word_length_distribution(cursor, song_id)
            result = cursor.fetchall()
            logger.info(f'Fetched word length distribution with {len(result)} different lengths')
            return result

    except Exception as e:
        logger.error(f"Failed to fetch word length distribution due to {e}")
        raise


def get_words_per_stanza(song_id: int) -> list:
    """
    Returns the number of words in each stanza of a song.
    :param song_id: The database ID of the song.
    :return: A list of tuples in the format: [(stanza_number, word_count), ...]
    """
    logger.info(f'Fetching word count per stanza for song id {song_id}')

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_words_per_stanza(cursor, song_id)
            result = cursor.fetchall()
            logger.info(f'Fetched statistics for {len(result)} stanzas in song id {song_id}')
            return result

    except Exception as e:
        logger.error(f'Failed to fetch word count per stanza for song id {song_id} due to {e}')
        raise
