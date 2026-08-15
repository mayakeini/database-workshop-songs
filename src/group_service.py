import logging
from typing import Any

from src.db import get_connection
from src.queries.general import (
    query_insert_group_word,
    query_select_word_id_by_text,
)
from src.queries.group_service_queries import (
    query_delete_group,
    query_delete_group_word_by_text,
    query_insert_group_returning_id,
    query_select_group_id_by_name,
    query_select_group_occurrences,
    query_select_group_words,
    query_select_groups,
    query_update_group,
)

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

    logger.info(f"Creating word group '{group_name}'")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query_select_group_id_by_name(cursor, group_name)

        existing_group = cursor.fetchone()

        if existing_group is not None:
            logger.warning(
                f"Group creation rejected because group '{group_name}' already exists",
            )

            raise ValueError(
                f"A group named '{group_name}' already exists."
            )

        group_id_var = cursor.var(int)

        query_insert_group_returning_id(
            cursor,
            group_name=group_name,
            description=description,
            group_id=group_id_var,
        )

        group_id = group_id_var.getvalue()[0]

        connection.commit()

        logger.info(f"Created word group '{group_name}' with id {group_id}")

        return group_id

    except ValueError:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()

        logger.exception(f"Failed to create group '{group_name}'")
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

    logger.info(f"Adding word '{word}' to group id {group_id}")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query_select_word_id_by_text(cursor, word)

        row = cursor.fetchone()

        if row is None:
            logger.warning(f"Word '{word}' does not exist in the database")

            raise ValueError(
                f"Word '{word}' does not exist in database"
            )

        word_id = row[0]

        query_insert_group_word(cursor, group_id, word_id)

        connection.commit()

        logger.info(f"Added word '{word}' to group id {group_id}")

    except Exception:
        connection.rollback()

        logger.exception(f"Failed to add word '{word}' to group id {group_id}")
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

    logger.info(f"Removing word '{word}' from group id {group_id}")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query_delete_group_word_by_text(cursor, group_id, word)

        removed = cursor.rowcount > 0

        connection.commit()

        if removed:
            logger.info(f"Removed word '{word}' from group id {group_id}")

        else:
            logger.warning(f"Word '{word}' was not found in group id {group_id}")

        return removed

    except Exception:
        connection.rollback()

        logger.exception(f"Failed to remove word '{word}' from group id {group_id}")
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
    logger.info(f'Fetching words for group id {group_id}')

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query_select_group_words(cursor, group_id)

        result = cursor.fetchall()

        logger.info(f'Fetched {len(result)} words for group id {group_id}')

        return result

    except Exception:
        logger.exception(f'Failed to fetch words for group id {group_id}')
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

        query_select_groups(cursor)

        result = cursor.fetchall()

        logger.info(f'Fetched {len(result)} word groups')

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
    logger.info(f'Fetching occurrences for group id {group_id}')

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query_select_group_occurrences(cursor, group_id)

        result = cursor.fetchall()

        logger.info(f'Fetched {len(result)} occurrences for group id {group_id}')

        return result

    except Exception:
        logger.exception(f'Failed to fetch occurrences for group id {group_id}')
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
        logger.warning(f'Attempted to update group id {group_id} with an empty name')

        raise ValueError(
            "Group name cannot be empty"
        )

    logger.info(f"Updating group id {group_id} to name '{group_name}'")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query_update_group(
            cursor,
            group_id=group_id,
            group_name=group_name,
            description=description,
        )

        updated = cursor.rowcount > 0

        connection.commit()

        if updated:
            logger.info(f'Group id {group_id} updated successfully')

        else:
            logger.warning(f'Group id {group_id} was not found')

        return updated

    except Exception:
        connection.rollback()

        logger.exception(f'Failed to update group id {group_id}')
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
    logger.info(f'Deleting group id {group_id}')

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query_delete_group(cursor, group_id)

        deleted = cursor.rowcount > 0

        connection.commit()

        if deleted:
            logger.info(f'Group id {group_id} deleted successfully')

        else:
            logger.warning(f'Group id {group_id} was not found')

        return deleted

    except Exception:
        connection.rollback()

        logger.exception(f'Failed to delete group id {group_id}')
        raise

    finally:
        connection.close()
