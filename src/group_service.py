import logging
from typing import Any

import oracledb

from src.db import get_database_service
from src.queries.db_queries import (
    query_delete_group,
    query_delete_group_word_by_text,
    query_insert_group_returning_id,
    query_insert_group_word,
    query_select_group_id_by_name,
    query_select_group_occurrences,
    query_select_group_words,
    query_select_groups,
    query_select_word_id_by_text,
    query_update_group,
)

logger = logging.getLogger(__name__)


def create_group(
    group_name: str,
    description: str | None = None,
    first_word: str = "",
) -> int:
    """
    Creates a new word group.

    Group names are treated as case-insensitively unique.

    Args:
        group_name: The name of the group.
        description: Optional description of the group.
        first_word: Required initial word, already present in the database.

    Returns:
        The ID of the newly created group.

    Raises:
        ValueError: If the group name is empty or already exists.
        Exception: If an unexpected database operation fails.
    """
    group_name = group_name.strip()
    first_word = first_word.strip().lower()

    if not first_word:
        logger.warning("Group creation rejected without an initial word")
        raise ValueError("Please enter at least one word for the group.")

    if not group_name:
        logger.warning(
            "Attempted to create a group with an empty name"
        )
        raise ValueError(
            "Group name cannot be empty."
        )

    logger.info(f"Creating word group '{group_name}'")

    try:
        with get_database_service().transaction() as cursor:
            query_select_group_id_by_name(cursor, group_name)

            existing_group = cursor.fetchone()

            if existing_group is not None:
                logger.warning(
                    f"Group creation rejected because group '{group_name}' already exists",
                )

                raise ValueError(
                    f"A group named '{group_name}' already exists."
                )

            query_select_word_id_by_text(cursor, first_word)
            first_word_row = cursor.fetchone()
            if first_word_row is None:
                logger.warning("Initial word '%s' is not in the database", first_word)
                raise ValueError(f"Word '{first_word}' does not exist in the database.")

            group_id_var = cursor.var(int)

            query_insert_group_returning_id(
                cursor,
                group_name=group_name,
                description=description,
                group_id=group_id_var,
            )

            group_id = group_id_var.getvalue()[0]
            query_insert_group_word(cursor, group_id, int(first_word_row[0]))

        logger.info(f"Created word group '{group_name}' with id {group_id}")

        return group_id

    except ValueError:
        raise

    except Exception:
        logger.exception(f"Failed to create group '{group_name}'")
        raise


def add_word_to_group(group_id: int, word: str) -> None:
    """Add a word to a group, rejecting duplicate memberships.

    Args:
        group_id: Target group identifier.
        word: Word to add.

    Returns:
        None.

    Raises:
        ValueError: Word is empty, absent from the database, or already in group.
        Exception: Unexpected database failure.
    """
    word = word.strip().lower()
    if not word:
        logger.warning("Empty word rejected for group id %s", group_id)
        raise ValueError("Please enter a word.")

    logger.info("Adding word '%s' to group %s", word, group_id)
    try:
        with get_database_service().transaction() as cursor:
            query_select_word_id_by_text(cursor, word)
            row = cursor.fetchone()
            if row is None:
                logger.warning("Unknown word '%s' for group %s", word, group_id)
                raise ValueError(f"Word '{word}' does not exist in the database.")

            word_id = row[0]
            query_select_group_words(cursor, group_id)
            if any(group_word_id == word_id for group_word_id, _ in cursor.fetchall()):
                logger.warning("Duplicate word '%s' in group %s", word, group_id)
                raise ValueError(f"Word '{word}' is already in this group.")

            try:
                query_insert_group_word(cursor, group_id, word_id)
            except oracledb.IntegrityError as exc:
                # Also handle concurrent requests racing after the SELECT.
                if exc.args and getattr(exc.args[0], "code", None) == 1:
                    logger.warning("Oracle rejected duplicate word '%s' for group %s", word, group_id)
                    raise ValueError(f"Word '{word}' is already in this group.") from exc
                raise

        logger.info("Word '%s' added to group %s", word, group_id)
    except ValueError:
        raise
    except Exception:
        logger.exception("Failed to add word '%s' to group %s", word, group_id)
        raise


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

    try:
        with get_database_service().transaction() as cursor:
            query_select_group_words(cursor, group_id)
            current_words = cursor.fetchall()
            if len(current_words) <= 1 and any(
                current_word.lower() == word for _, current_word in current_words
            ):
                logger.warning("Refusing to remove last word from group %s", group_id)
                raise ValueError(
                    "A group must contain at least one word. "
                    "Delete the group instead."
                )
            query_delete_group_word_by_text(cursor, group_id, word)

            removed = cursor.rowcount > 0

        if removed:
            logger.info(f"Removed word '{word}' from group id {group_id}")

        else:
            logger.warning(f"Word '{word}' was not found in group id {group_id}")

        return removed

    except Exception:
        logger.exception(f"Failed to remove word '{word}' from group id {group_id}")
        raise


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

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_group_words(cursor, group_id)

            result = cursor.fetchall()

            logger.info(f'Fetched {len(result)} words for group id {group_id}')

            return result

    except Exception:
        logger.exception(f'Failed to fetch words for group id {group_id}')
        raise


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

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_groups(cursor)

            result = cursor.fetchall()

            logger.info(f'Fetched {len(result)} word groups')

            return result

    except Exception:
        logger.exception(
            "Failed to fetch word groups"
        )
        raise


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

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_group_occurrences(cursor, group_id)

            result = cursor.fetchall()

            logger.info(f'Fetched {len(result)} occurrences for group id {group_id}')

            return result

    except Exception:
        logger.exception(f'Failed to fetch occurrences for group id {group_id}')
        raise


def update_group(
    group_id: int,
    group_name: str,
    description: str | None = None,
) -> bool:
    """Update group details while enforcing a case-insensitive unique name.

    Args:
        group_id: ID of the group being edited.
        group_name: Proposed group name.
        description: Optional group description.

    Returns:
        True if updated, False if the group no longer exists.

    Raises:
        ValueError: If the name is blank or used by another group.
        oracledb.DatabaseError: On other Oracle errors.
    """
    group_name = group_name.strip()
    if not group_name:
        logger.warning("Group update rejected: empty name for group id %s", group_id)
        raise ValueError("Group name is required.")

    logger.info("Updating group id %s to name '%s'", group_id, group_name)
    try:
        with get_database_service().transaction() as cursor:
            query_select_group_id_by_name(cursor, group_name)
            existing_group = cursor.fetchone()
            if existing_group is not None and int(existing_group[0]) != group_id:
                logger.warning(
                    "Group name '%s' is already used by group id %s",
                    group_name, existing_group[0],
                )
                raise ValueError(f"A group named '{group_name}' already exists.")

            try:
                query_update_group(
                    cursor,
                    group_id=group_id,
                    group_name=group_name,
                    description=description,
                )
            except oracledb.IntegrityError as error:
                # Also handle a concurrent rename/creation between SELECT and UPDATE.
                if error.args and getattr(error.args[0], "code", None) == 1:
                    logger.warning(
                        "Oracle rejected duplicate name '%s' for group %s",
                        group_name, group_id,
                    )
                    raise ValueError(
                        f"A group named '{group_name}' already exists."
                    ) from error
                raise

            updated = cursor.rowcount > 0

        if updated:
            logger.info("Group id %s updated successfully", group_id)
        else:
            logger.warning("Group id %s was not found during update", group_id)
        return updated
    except ValueError:
        raise
    except Exception:
        logger.exception("Failed to update group id %s", group_id)
        raise


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

    try:
        with get_database_service().transaction() as cursor:
            query_delete_group(cursor, group_id)

            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f'Group id {group_id} deleted successfully')

        else:
            logger.warning(f'Group id {group_id} was not found')

        return deleted

    except Exception:
        logger.exception(f'Failed to delete group id {group_id}')
        raise
