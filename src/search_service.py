import logging

from src.db import get_database_service
from src.queries.db_queries import (
    query_search_songs,
    query_search_word_occurrences,
    query_select_context_lines,
    query_select_line_tokens_by_global_number,
    query_select_line_tokens_by_stanza_position,
    query_select_word_by_position,
    query_select_word_index,
)

logger = logging.getLogger(__name__)


def search_songs(title=None, artist=None, album=None, publication_year=None):
    """
    Search songs based on title and artist & album title
    :param title: title of the song
    :param artist: song's artist
    :param album: song's album
    :param publication_year: song's publication year
    :return:
    """
    with get_database_service().read_cursor() as cursor:
        query_search_songs(
            cursor,
            title=title,
            artist=artist,
            album=album,
            publication_year=publication_year,
        )

        return cursor.fetchall()


def search_word(word: str):
    """
    Search words
    :param word: str of the word
    :return:
    """
    with get_database_service().read_cursor() as cursor:
        query_search_word_occurrences(cursor, word)

        return cursor.fetchall()


def get_context(song_id: int, global_line_number: int) -> dict:
    """
    Get context for the song
    :param song_id: int of the song
    :param global_line_number: int of the global line number
    :return: dictionary of the context for the song
    """
    with get_database_service().read_cursor() as cursor:
        query_select_context_lines(
            cursor,
            song_id,
            global_line_number - 1,
            global_line_number + 1,
        )

        rows = cursor.fetchall()

        lines = {}

        for line_number, position, token in rows:
            if line_number not in lines:
                lines[line_number] = []

            lines[line_number].append(token)

        return {
            line_number: " ".join(tokens)
            for line_number, tokens in lines.items()
        }


def get_word_index(
    song_id: int | None = None,
    group_id: int | None = None,
) -> list[tuple]:
    """Return word occurrences optionally filtered by song and word group.

    Args:
        song_id: Song to filter by, or None for all songs.
        group_id: Word group to filter by, or None for all words.

    Returns:
        Occurrence rows containing word, song and location fields.
    """
    logger.info(
        "Fetching word index: song_id=%s, group_id=%s",
        song_id,
        group_id,
    )
    with get_database_service().read_cursor() as cursor:
        query_select_word_index(cursor, song_id=song_id, group_id=group_id)
        rows = cursor.fetchall()
        logger.info("Fetched %s word index rows", len(rows))
        return rows


def find_line_by_global_number(song_id: int, global_line_number:int) -> dict:
    """
    Find line by song id and global line number
    :param song_id: int of the song id
    :param global_line_number: int of the global line number
    :return: dictionary of the context for the song
    """
    logger.info(fr"Find the line in line number: {global_line_number} of the song id: {song_id}")
    with get_database_service().read_cursor() as cursor:
        query_select_line_tokens_by_global_number(
            cursor,
            song_id,
            global_line_number,
        )

        tokens = [row[0] for row in cursor.fetchall()]

        if not tokens:
            return None

        return " ".join(tokens)


def find_line_by_stanza_position(song_id: int, stanza_number: int, line_number_in_stanza: int) -> dict:
    """
    Get line by song id and stanza position
    :param song_id: int of the song id
    :param stanza_number: int of the stanza number
    :param line_number_in_stanza: int of the stanza number
    :return: dictionary of the context for the song
    """
    logger.info(fr"Find the line of the song id {song_id} and stanza number {stanza_number}. Line number in stanza is {line_number_in_stanza}")
    with get_database_service().read_cursor() as cursor:
        query_select_line_tokens_by_stanza_position(
            cursor,
            song_id,
            stanza_number,
            line_number_in_stanza,
        )

        tokens = [row[0] for row in cursor.fetchall()]

        if not tokens:
            return None

        return " ".join(tokens)


def find_word_by_position(song_id: int, global_line_number: int, position_in_line: int) -> dict:
    """
    Find word by song id, global line number and position in line
    :param song_id: int of the song id
    :param global_line_number: int of the global line number
    :param position_in_line: int of the position in line
    :return: dictionary of the context for the song
    """
    logger.info(fr"Find the word in line number: {position_in_line} of the song id: {song_id}. The word position is {global_line_number}")
    with get_database_service().read_cursor() as cursor:
        query_select_word_by_position(
            cursor,
            song_id,
            global_line_number,
            position_in_line,
        )

        return cursor.fetchone()
