import logging
from typing import List, Tuple

from src.db import get_database_service
from src.queries.db_queries import (
    query_delete_phrase,
    query_delete_phrase_occurrences,
    query_insert_phrase_occurrence,
    query_insert_phrase_returning_id,
    query_select_context_lines,
    query_select_phrase_occurrences,
    query_select_phrase_search_occurrences,
    query_select_phrases,
)
from src.text_parser import _normalize_word

logger = logging.getLogger(__name__)


def create_phrase(phrase_name: str, phrase_text: str) -> int:
    """
    Creates a new phrase definition in the database.

    Args:
        phrase_name: A unique name for the phrase.
        phrase_text: The textual phrase to search for.

    Returns:
        The ID of the newly created phrase.

    Raises:
        ValueError: If the phrase text is empty.
        Exception: If the database operation fails.
    """
    if not phrase_text.strip():
        logger.warning("Attempted to create an empty phrase")
        raise ValueError("Phrase text cannot be empty")

    logger.info(f"Creating phrase '{phrase_name}' with text '{phrase_text}'")

    try:
        with get_database_service().transaction() as cursor:
            phrase_id_var = cursor.var(int)

            query_insert_phrase_returning_id(
                cursor,
                phrase_name=phrase_name,
                phrase_text=phrase_text,
                phrase_id=phrase_id_var,
            )

            phrase_id = phrase_id_var.getvalue()[0]

        logger.info(f"Created phrase '{phrase_name}' with id {phrase_id}")

        return phrase_id

    except Exception:
        logger.exception(f"Failed to create phrase '{phrase_name}'")
        raise

def find_phrase_occurrences(
    phrase_id: int,
    phrase_text: str,
) -> List[Tuple[int, int, int, int]]:
    """
    Searches for all occurrences of a phrase in the loaded songs.

    A phrase occurrence is considered valid when all its words appear
    consecutively in the same line and in the same song.

    Args:
        phrase_id: The database ID of the phrase.
        phrase_text: The phrase text to search for.

    Returns:
        A list of tuples containing:
        (
            song_id,
            start_occurrence_id,
            end_occurrence_id,
            global_line_number
        )

    Raises:
        ValueError: If the phrase contains no valid words.
        Exception: If the database operation fails.
    """
    normalized_words = [
        _normalize_word(token)
        for token in phrase_text.split()
    ]

    normalized_words = [
        word
        for word in normalized_words
        if word
    ]

    if not normalized_words:
        logger.warning(f'Phrase {phrase_id} contains no searchable words')
        raise ValueError("Phrase contains no valid words")

    logger.info(
        f'Searching for phrase id {phrase_id} containing {len(normalized_words)} words',
    )

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_phrase_search_occurrences(cursor)

            rows = cursor.fetchall()

            occurrences = []

            phrase_length = len(normalized_words)

            for index in range(len(rows) - phrase_length + 1):
                candidate = rows[index:index + phrase_length]

                candidate_words = [
                    row[4]
                    for row in candidate
                ]

                if candidate_words != normalized_words:
                    continue

                song_ids = {
                    row[1]
                    for row in candidate
                }

                line_numbers = {
                    row[2]
                    for row in candidate
                }

                positions = [
                    row[3]
                    for row in candidate
                ]

                same_song = len(song_ids) == 1
                same_line = len(line_numbers) == 1

                consecutive_positions = positions == list(
                    range(
                        positions[0],
                        positions[0] + phrase_length,
                    )
                )

                if not (
                    same_song
                    and same_line
                    and consecutive_positions
                ):
                    continue

                song_id = candidate[0][1]
                global_line_number = candidate[0][2]
                start_occurrence_id = candidate[0][0]
                end_occurrence_id = candidate[-1][0]

                occurrences.append(
                    (
                        song_id,
                        start_occurrence_id,
                        end_occurrence_id,
                        global_line_number,
                    )
                )

            logger.info(f'Found {len(occurrences)} occurrences for phrase id {phrase_id}')

            return occurrences

    except Exception:
        logger.exception(f'Failed while searching for phrase id {phrase_id}')
        raise

def save_phrase_occurrences(
    phrase_id: int,
    occurrences: List[Tuple[int, int, int, int]],
) -> int:
    """
    Saves phrase occurrences in the database.

    Args:
        phrase_id: The database ID of the phrase.
        occurrences: A list of phrase occurrences in the format:
            (
                song_id,
                start_occurrence_id,
                end_occurrence_id,
                global_line_number
            )

    Returns:
        The number of occurrences saved.

    Raises:
        Exception: If the database operation fails.
    """
    logger.info(f'Saving {len(occurrences)} occurrences for phrase id {phrase_id}')

    try:
        with get_database_service().transaction() as cursor:
            query_delete_phrase_occurrences(cursor, phrase_id)

            for (
                song_id,
                start_occurrence_id,
                end_occurrence_id,
                _,
            ) in occurrences:
                query_insert_phrase_occurrence(
                    cursor,
                    phrase_id=phrase_id,
                    song_id=song_id,
                    start_occurrence_id=start_occurrence_id,
                    end_occurrence_id=end_occurrence_id,
                )

        logger.info(f'Saved {len(occurrences)} phrase occurrences successfully')

        return len(occurrences)

    except Exception:
        logger.exception(f'Failed to save occurrences for phrase id {phrase_id}')
        raise

def create_and_search_phrase(
    phrase_name: str,
    phrase_text: str,
) -> int:
    """
    Creates a phrase, searches for all of its occurrences,
    and stores the found occurrences in the database.

    Args:
        phrase_name: A unique name for the phrase.
        phrase_text: The phrase to search for.

    Returns:
        The ID of the created phrase.

    Raises:
        ValueError: If the phrase text is invalid.
        Exception: If any database operation fails.
    """
    logger.info(f"Starting creation and search for phrase '{phrase_name}'")

    phrase_id = create_phrase(
        phrase_name=phrase_name,
        phrase_text=phrase_text,
    )

    occurrences = find_phrase_occurrences(
        phrase_id=phrase_id,
        phrase_text=phrase_text,
    )

    save_phrase_occurrences(
        phrase_id=phrase_id,
        occurrences=occurrences,
    )

    logger.info(f"Finished processing phrase '{phrase_name}'")

    return phrase_id

def get_phrases() -> list[tuple[int, str, str, object]]:
    """
    Returns all phrase definitions stored in the database.

    Returns:
        A list of tuples in the format:
        (
            phrase_id,
            phrase_name,
            phrase_text,
            creation_date
        )

    Raises:
        Exception: If the database query fails.
    """
    logger.info("Fetching all phrases")

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_phrases(cursor)

            result = cursor.fetchall()

            logger.info(f'Fetched {len(result)} phrases')

            return result

    except Exception:
        logger.exception("Failed to fetch phrases")
        raise

def delete_phrase(phrase_id: int) -> bool:
    """
    Deletes a phrase and all of its stored occurrences.

    Args:
        phrase_id: The ID of the phrase to delete.

    Returns:
        True if the phrase was deleted, False if it did not exist.

    Raises:
        Exception: If the database operation fails.
    """
    logger.info(f'Deleting phrase id {phrase_id}')

    try:
        with get_database_service().transaction() as cursor:
            query_delete_phrase(cursor, phrase_id)

            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f'Phrase id {phrase_id} deleted successfully')
        else:
            logger.warning(f'Phrase id {phrase_id} was not found')

        return deleted

    except Exception:
        logger.exception(f'Failed to delete phrase id {phrase_id}')
        raise

def get_phrase_occurrences(
    phrase_id: int,
) -> list[tuple[int, str, int, int, int]]:
    """
    Returns all stored occurrences of a phrase.

    Args:
        phrase_id: The ID of the phrase.

    Returns:
        A list of tuples in the format:
        (
            song_id,
            song_title,
            global_line_number,
            start_position_in_line,
            end_position_in_line
        )

    Raises:
        Exception: If the database query fails.
    """
    logger.info(f'Fetching occurrences for phrase id {phrase_id}')

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_phrase_occurrences(cursor, phrase_id)

            result = cursor.fetchall()

            logger.info(f'Fetched {len(result)} occurrences for phrase id {phrase_id}')

            return result

    except Exception:
        logger.exception(f'Failed to fetch occurrences for phrase id {phrase_id}')
        raise

def get_phrase_occurrences_with_context(
    phrase_id: int,
) -> list[dict[str, object]]:
    """
    Returns phrase occurrences together with their textual context.

    The context includes the previous line, the line containing
    the phrase, and the next line when they exist.

    Args:
        phrase_id: The ID of the phrase.

    Returns:
        A list of dictionaries containing occurrence information
        and surrounding text.

    Raises:
        Exception: If retrieving the occurrences or context fails.
    """
    logger.info(f'Fetching occurrences with context for phrase id {phrase_id}')

    occurrences = get_phrase_occurrences(phrase_id)

    results: list[dict[str, object]] = []

    try:
        with get_database_service().read_cursor() as cursor:
            for (
                song_id,
                song_title,
                global_line_number,
                start_position,
                end_position,
            ) in occurrences:

                query_select_context_lines(
                    cursor,
                    song_id,
                    global_line_number - 1,
                    global_line_number + 1,
                )

                rows = cursor.fetchall()

                lines: dict[int, list[str]] = {}

                for line_number, _, token in rows:
                    lines.setdefault(line_number, []).append(token)

                context = {
                    line_number: " ".join(tokens)
                    for line_number, tokens in lines.items()
                }

                results.append(
                    {
                        "song_id": song_id,
                        "song_title": song_title,
                        "global_line_number": global_line_number,
                        "start_position": start_position,
                        "end_position": end_position,
                        "context": context,
                    }
                )

            logger.info(
                f'Built context for {len(results)} occurrences of phrase id {phrase_id}',
            )

            return results

    except Exception:
        logger.exception(f'Failed to build context for phrase id {phrase_id}')
        raise
