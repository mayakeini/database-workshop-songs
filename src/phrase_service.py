import logging
from typing import List, Tuple

from src.db import get_connection
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

    logger.info(
        "Creating phrase '%s' with text '%s'",
        phrase_name,
        phrase_text,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()
        phrase_id_var = cursor.var(int)

        cursor.execute(
            """
            INSERT INTO phrases (
                phrase_name,
                phrase_text
            )
            VALUES (
                :phrase_name,
                :phrase_text
            )
            RETURNING phrase_id INTO :phrase_id
            """,
            phrase_name=phrase_name,
            phrase_text=phrase_text,
            phrase_id=phrase_id_var,
        )

        phrase_id = phrase_id_var.getvalue()[0]

        connection.commit()

        logger.info(
            "Created phrase '%s' with id %s",
            phrase_name,
            phrase_id,
        )

        return phrase_id

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to create phrase '%s'",
            phrase_name,
        )
        raise

    finally:
        connection.close()

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
        logger.warning(
            "Phrase %s contains no searchable words",
            phrase_id,
        )
        raise ValueError("Phrase contains no valid words")

    logger.info(
        "Searching for phrase id %s containing %s words",
        phrase_id,
        len(normalized_words),
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                wo.occurrence_id,
                wo.song_id,
                wo.global_line_number,
                wo.position_in_line,
                w.text
            FROM word_occurrences wo
            JOIN words w
                ON wo.word_id = w.word_id
            ORDER BY
                wo.song_id,
                wo.global_line_number,
                wo.position_in_line
            """
        )

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

        logger.info(
            "Found %s occurrences for phrase id %s",
            len(occurrences),
            phrase_id,
        )

        return occurrences

    except Exception:
        logger.exception(
            "Failed while searching for phrase id %s",
            phrase_id,
        )
        raise

    finally:
        connection.close()

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
    logger.info(
        "Saving %s occurrences for phrase id %s",
        len(occurrences),
        phrase_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM phrase_occurrences
            WHERE phrase_id = :phrase_id
            """,
            phrase_id=phrase_id,
        )

        for (
            song_id,
            start_occurrence_id,
            end_occurrence_id,
            _,
        ) in occurrences:
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

        connection.commit()

        logger.info(
            "Saved %s phrase occurrences successfully",
            len(occurrences),
        )

        return len(occurrences)

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to save occurrences for phrase id %s",
            phrase_id,
        )
        raise

    finally:
        connection.close()

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
    logger.info(
        "Starting creation and search for phrase '%s'",
        phrase_name,
    )

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

    logger.info(
        "Finished processing phrase '%s'",
        phrase_name,
    )

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

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                phrase_id,
                phrase_name,
                phrase_text,
                TO_CHAR(
                    creation_date,
                    'YYYY-MM-DD HH24:MI:SS TZH:TZM'
                ) AS creation_date
            FROM phrases
            ORDER BY phrase_name
            """
        )

        result = cursor.fetchall()

        logger.info(
            "Fetched %s phrases",
            len(result),
        )

        return result

    except Exception:
        logger.exception("Failed to fetch phrases")
        raise

    finally:
        connection.close()

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
    logger.info(
        "Deleting phrase id %s",
        phrase_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM phrases
            WHERE phrase_id = :phrase_id
            """,
            phrase_id=phrase_id,
        )

        deleted = cursor.rowcount > 0

        connection.commit()

        if deleted:
            logger.info(
                "Phrase id %s deleted successfully",
                phrase_id,
            )
        else:
            logger.warning(
                "Phrase id %s was not found",
                phrase_id,
            )

        return deleted

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to delete phrase id %s",
            phrase_id,
        )
        raise

    finally:
        connection.close()

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
    logger.info(
        "Fetching occurrences for phrase id %s",
        phrase_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                s.song_id,
                s.title,
                start_occ.global_line_number,
                start_occ.position_in_line,
                end_occ.position_in_line
            FROM phrase_occurrences po
            JOIN songs s
                ON po.song_id = s.song_id
            JOIN word_occurrences start_occ
                ON po.start_occurrence_id = start_occ.occurrence_id
            JOIN word_occurrences end_occ
                ON po.end_occurrence_id = end_occ.occurrence_id
            WHERE po.phrase_id = :phrase_id
            ORDER BY
                s.song_id,
                start_occ.position_in_song
            """,
            phrase_id=phrase_id,
        )

        result = cursor.fetchall()

        logger.info(
            "Fetched %s occurrences for phrase id %s",
            len(result),
            phrase_id,
        )

        return result

    except Exception:
        logger.exception(
            "Failed to fetch occurrences for phrase id %s",
            phrase_id,
        )
        raise

    finally:
        connection.close()

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
    logger.info(
        "Fetching occurrences with context for phrase id %s",
        phrase_id,
    )

    occurrences = get_phrase_occurrences(phrase_id)

    results: list[dict[str, object]] = []

    connection = get_connection()

    try:
        cursor = connection.cursor()

        for (
            song_id,
            song_title,
            global_line_number,
            start_position,
            end_position,
        ) in occurrences:

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
                previous_line=global_line_number - 1,
                next_line=global_line_number + 1,
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
            "Built context for %s occurrences of phrase id %s",
            len(results),
            phrase_id,
        )

        return results

    except Exception:
        logger.exception(
            "Failed to build context for phrase id %s",
            phrase_id,
        )
        raise

    finally:
        connection.close()
