import logging
from typing import Any

from src.db import get_connection

logger = logging.getLogger(__name__)


def create_group(
    group_name: str,
    description: str | None = None,
) -> int:
    """
    Creates a new word group.

    Group names are treated as case-insensitively unique.

    Args:
        group_name: The name of the group.
        description: Optional description of the group.

    Returns:
        The ID of the newly created group.

    Raises:
        ValueError: If the group name is empty or already exists.
        Exception: If an unexpected database operation fails.
    """
    group_name = group_name.strip()

    if not group_name:
        logger.warning(
            "Attempted to create a group with an empty name"
        )
        raise ValueError(
            "Group name cannot be empty."
        )

    logger.info(
        "Creating word group '%s'",
        group_name,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT group_id
            FROM word_groups
            WHERE LOWER(group_name) = LOWER(:group_name)
            """,
            group_name=group_name,
        )

        existing_group = cursor.fetchone()

        if existing_group is not None:
            logger.warning(
                "Group creation rejected because group '%s' already exists",
                group_name,
            )

            raise ValueError(
                f"A group named '{group_name}' already exists."
            )

        group_id_var = cursor.var(int)

        cursor.execute(
            """
            INSERT INTO word_groups (
                group_name,
                description
            )
            VALUES (
                :group_name,
                :description
            )
            RETURNING group_id INTO :group_id
            """,
            group_name=group_name,
            description=description,
            group_id=group_id_var,
        )

        group_id = group_id_var.getvalue()[0]

        connection.commit()

        logger.info(
            "Created word group '%s' with id %s",
            group_name,
            group_id,
        )

        return group_id

    except ValueError:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()

        logger.exception(
            "Failed to create group '%s'",
            group_name,
        )
        raise

    finally:
        connection.close()


def add_word_to_group(
    group_id: int,
    word: str,
) -> None:
    """
    Adds an existing word to a word group.

    Args:
        group_id: The ID of the target group.
        word: The word to add.

    Returns:
        None.

    Raises:
        ValueError: If the word does not exist in the database.
        Exception: If the database operation fails.
    """
    word = word.strip().lower()

    logger.info(
        "Adding word '%s' to group id %s",
        word,
        group_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT word_id
            FROM words
            WHERE text = :word
            """,
            word=word,
        )

        row = cursor.fetchone()

        if row is None:
            logger.warning(
                "Word '%s' does not exist in the database",
                word,
            )

            raise ValueError(
                f"Word '{word}' does not exist in database"
            )

        word_id = row[0]

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

        connection.commit()

        logger.info(
            "Added word '%s' to group id %s",
            word,
            group_id,
        )

    except Exception:
        connection.rollback()

        logger.exception(
            "Failed to add word '%s' to group id %s",
            word,
            group_id,
        )
        raise

    finally:
        connection.close()


def remove_word_from_group(
    group_id: int,
    word: str,
) -> bool:
    """
    Removes a word from a word group.

    Args:
        group_id: The ID of the group.
        word: The word to remove.

    Returns:
        True if the word was removed, False otherwise.

    Raises:
        Exception: If the database operation fails.
    """
    word = word.strip().lower()

    logger.info(
        "Removing word '%s' from group id %s",
        word,
        group_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM group_words
            WHERE group_id = :group_id
              AND word_id = (
                    SELECT word_id
                    FROM words
                    WHERE text = :word
              )
            """,
            group_id=group_id,
            word=word,
        )

        removed = cursor.rowcount > 0

        connection.commit()

        if removed:
            logger.info(
                "Removed word '%s' from group id %s",
                word,
                group_id,
            )

        else:
            logger.warning(
                "Word '%s' was not found in group id %s",
                word,
                group_id,
            )

        return removed

    except Exception:
        connection.rollback()

        logger.exception(
            "Failed to remove word '%s' from group id %s",
            word,
            group_id,
        )
        raise

    finally:
        connection.close()


def get_group_words(
    group_id: int,
) -> list[tuple[int, str]]:
    """
    Returns all words assigned to a word group.

    Args:
        group_id: The ID of the group.

    Returns:
        A list of tuples in the format:
        [
            (word_id, word_text),
            ...
        ]

    Raises:
        Exception: If the database query fails.
    """
    logger.info(
        "Fetching words for group id %s",
        group_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                w.word_id,
                w.text
            FROM group_words gw
            JOIN words w
                ON gw.word_id = w.word_id
            WHERE gw.group_id = :group_id
            ORDER BY w.text
            """,
            group_id=group_id,
        )

        result = cursor.fetchall()

        logger.info(
            "Fetched %s words for group id %s",
            len(result),
            group_id,
        )

        return result

    except Exception:
        logger.exception(
            "Failed to fetch words for group id %s",
            group_id,
        )
        raise

    finally:
        connection.close()


def get_groups() -> list[tuple[Any, ...]]:
    """
    Returns all word groups.

    Returns:
        A list containing the stored word groups.

    Raises:
        Exception: If the database query fails.
    """
    logger.info(
        "Fetching all word groups"
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                group_id,
                group_name,
                description,
                TO_CHAR(
                    creation_date,
                    'YYYY-MM-DD HH24:MI:SS TZH:TZM'
                ) AS creation_date
            FROM word_groups
            ORDER BY group_name
            """
        )

        result = cursor.fetchall()

        logger.info(
            "Fetched %s word groups",
            len(result),
        )

        return result

    except Exception:
        logger.exception(
            "Failed to fetch word groups"
        )
        raise

    finally:
        connection.close()


def get_group_occurrences(
    group_id: int,
) -> list[tuple[Any, ...]]:
    """
    Returns all occurrences of words belonging to a word group.

    Args:
        group_id: The ID of the group.

    Returns:
        A list containing occurrences of the group's words.

    Raises:
        Exception: If the database query fails.
    """
    logger.info(
        "Fetching occurrences for group id %s",
        group_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                w.text,
                s.song_id,
                s.title,
                st.stanza_number,
                wo.global_line_number,
                wo.line_number_in_stanza,
                wo.position_in_line,
                wo.original_token
            FROM group_words gw
            JOIN words w
                ON gw.word_id = w.word_id
            JOIN word_occurrences wo
                ON w.word_id = wo.word_id
            JOIN songs s
                ON wo.song_id = s.song_id
            JOIN stanzas st
                ON wo.stanza_id = st.stanza_id
            WHERE gw.group_id = :group_id
            ORDER BY
                w.text,
                s.song_id,
                wo.position_in_song
            """,
            group_id=group_id,
        )

        result = cursor.fetchall()

        logger.info(
            "Fetched %s occurrences for group id %s",
            len(result),
            group_id,
        )

        return result

    except Exception:
        logger.exception(
            "Failed to fetch occurrences for group id %s",
            group_id,
        )
        raise

    finally:
        connection.close()


def update_group(
    group_id: int,
    group_name: str,
    description: str | None = None,
) -> bool:
    """
    Updates the name and description of an existing word group.

    Args:
        group_id: The ID of the group to update.
        group_name: The new group name.
        description: The new optional group description.

    Returns:
        True if a group was updated, False if the group does not exist.

    Raises:
        ValueError: If the group name is empty.
        Exception: If the database operation fails.
    """
    group_name = group_name.strip()

    if not group_name:
        logger.warning(
            "Attempted to update group id %s with an empty name",
            group_id,
        )

        raise ValueError(
            "Group name cannot be empty"
        )

    logger.info(
        "Updating group id %s to name '%s'",
        group_id,
        group_name,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE word_groups
            SET
                group_name = :group_name,
                description = :description
            WHERE group_id = :group_id
            """,
            group_name=group_name,
            description=description,
            group_id=group_id,
        )

        updated = cursor.rowcount > 0

        connection.commit()

        if updated:
            logger.info(
                "Group id %s updated successfully",
                group_id,
            )

        else:
            logger.warning(
                "Group id %s was not found",
                group_id,
            )

        return updated

    except Exception:
        connection.rollback()

        logger.exception(
            "Failed to update group id %s",
            group_id,
        )
        raise

    finally:
        connection.close()


def delete_group(
    group_id: int,
) -> bool:
    """
    Deletes a word group.

    Words themselves are not deleted. Only the group and its
    word associations are removed.

    Args:
        group_id: The ID of the group to delete.

    Returns:
        True if the group was deleted, False if it did not exist.

    Raises:
        Exception: If the database operation fails.
    """
    logger.info(
        "Deleting group id %s",
        group_id,
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM word_groups
            WHERE group_id = :group_id
            """,
            group_id=group_id,
        )

        deleted = cursor.rowcount > 0

        connection.commit()

        if deleted:
            logger.info(
                "Group id %s deleted successfully",
                group_id,
            )

        else:
            logger.warning(
                "Group id %s was not found",
                group_id,
            )

        return deleted

    except Exception:
        connection.rollback()

        logger.exception(
            "Failed to delete group id %s",
            group_id,
        )
        raise

    finally:
        connection.close()
