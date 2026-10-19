import oracledb
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
    query_select_song_word_occurrences_for_phrases,
)
from src.text_parser import _normalize_word

logger = logging.getLogger(__name__)


def refresh_existing_phrases_for_song(
    cursor: oracledb.Cursor,
    song_id: int,
) -> int:
    """Add occurrences of every existing phrase found in a newly uploaded song.

    The caller owns the transaction. This method must run with the SAME cursor
    used to insert the song so all changes commit or roll back together.
    Existing occurrences in other songs are left untouched.

    Args:
        cursor: The open cursor from the song upload transaction.
        song_id: Database ID of the newly inserted song.

    Returns:
        Number of newly inserted phrase occurrences.
    """
    logger.info("Updating existing phrases for new song id %s", song_id)
    query_select_phrases(cursor)
    phrases = [(row[0], row[2]) for row in cursor.fetchall()]
    if not phrases:
        logger.info("No existing phrases to update for song id %s", song_id)
        return 0

    query_select_song_word_occurrences_for_phrases(cursor, song_id)
    rows = cursor.fetchall()
    inserted_count = 0

    for phrase_id, phrase_text in phrases:
        words = [
            normalized
            for token in phrase_text.split()
            if (normalized := _normalize_word(token))
        ]
        if not words:
            logger.warning("Skipping phrase id %s without valid words", phrase_id)
            continue

        for index in range(len(rows) - len(words) + 1):
            candidate = rows[index:index + len(words)]
            if [row[4] for row in candidate] != words:
                continue
            first_line = candidate[0][2]
            if any(row[2] != first_line for row in candidate):
                continue
            first_position = candidate[0][3]
            if any(row[3] != first_position + offset for offset, row in enumerate(candidate)):
                continue

            query_insert_phrase_occurrence(
                cursor,
                phrase_id=phrase_id,
                song_id=song_id,
                start_occurrence_id=candidate[0][0],
                end_occurrence_id=candidate[-1][0],
            )
            inserted_count += 1

    logger.info(
        "Updated %s phrases with %s occurrences in new song id %s",
        len(phrases), inserted_count, song_id,
    )
    return inserted_count


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

            try:
                query_insert_phrase_returning_id(
                    cursor,
                    phrase_name=phrase_name,
                    phrase_text=phrase_text,
                    phrase_id=phrase_id_var,
                )
            except oracledb.IntegrityError as error:
                oracle_error = error.args[0]
                if getattr(oracle_error, "code", None) == 1:
                    logger.warning("Phrase name '%s' already exists", phrase_name)
                    raise ValueError(
                        f"A phrase named '{phrase_name}' already exists."
                    ) from error
                raise

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
    """Create a phrase and all its occurrences as one atomic transaction.

    Searches consecutive normalized words within the same song and line.
    The database service commits once, after all inserts succeed, and rolls
    back the phrase definition and every occurrence if any step fails.

    Args:
        phrase_name: Unique name for the new phrase.
        phrase_text: Text whose consecutive occurrences should be stored.

    Returns:
        ID of the newly created phrase.

    Raises:
        ValueError: If the name or phrase contains no usable text.
        Exception: If any query or insert fails (the transaction is rolled back).
    """
    phrase_name = phrase_name.strip()
    phrase_text = phrase_text.strip()

    normalized_words = [
        normalized
        for token in phrase_text.split()
        if (normalized := _normalize_word(token))
    ]
    if not phrase_name:
        logger.warning("Phrase creation rejected: empty name")
        raise ValueError("Phrase name cannot be empty")
    if not normalized_words:
        logger.warning("Phrase creation rejected: no searchable words")
        raise ValueError("Phrase contains no valid words")

    logger.info("Creating phrase '%s' and searching all occurrences atomically", phrase_name)

    try:
        with get_database_service().transaction() as cursor:
            phrase_id_var = cursor.var(int)
            try:
                query_insert_phrase_returning_id(
                    cursor,
                    phrase_name=phrase_name,
                    phrase_text=phrase_text,
                    phrase_id=phrase_id_var,
                )
            except oracledb.IntegrityError as error:
                oracle_error = error.args[0]
                if getattr(oracle_error, "code", None) == 1:
                    logger.warning("Phrase name '%s' already exists", phrase_name)
                    raise ValueError(
                        f"A phrase named '{phrase_name}' already exists."
                    ) from error
                raise
            phrase_id = phrase_id_var.getvalue()[0]

            query_select_phrase_search_occurrences(cursor)
            rows = cursor.fetchall()
            phrase_length = len(normalized_words)
            saved_count = 0

            for index in range(len(rows) - phrase_length + 1):
                candidate = rows[index:index + phrase_length]
                if [row[4] for row in candidate] != normalized_words:
                    continue

                first_song_id = candidate[0][1]
                first_line_number = candidate[0][2]
                first_position = candidate[0][3]

                if any(
                    row[1] != first_song_id
                    or row[2] != first_line_number
                    or row[3] != first_position + offset
                    for offset, row in enumerate(candidate)
                ):
                    continue

                query_insert_phrase_occurrence(
                    cursor,
                    phrase_id=phrase_id,
                    song_id=first_song_id,
                    start_occurrence_id=candidate[0][0],
                    end_occurrence_id=candidate[-1][0],
                )
                saved_count += 1

        logger.info(
            "Created phrase '%s' (id=%s) with %s occurrences in one transaction",
            phrase_name,
            phrase_id,
            saved_count,
        )
        return phrase_id

    except Exception:
        logger.exception("Atomic phrase creation failed for '%s'", phrase_name)
        raise

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
