import logging
from typing import Any
import oracledb
from src.db import get_database_service
from src.queries.db_queries import query_delete_group,
    query_delete_group_word_by_text, query_insert_group_returning_id,
    query_insert_group_word, query_select_group_id_by_name, query_select_group_occurrences,
    query_select_group_words, query_select_groups,
    query_select_word_id_by_text, query_update_group


logger = logging.getLogger(__name__)


def create_group(group_name: str, description: str | None = None, first_word: str = "") -> int:
    """
    Creates a new word group.
    Group names are treated as case-insensitively unique.
    :param group_name: The name of the group.
    :param description: Optional description of the group.
    :param first_word: Required initial word, already present in the database.
    :return: The ID of the newly created group.
    """
    group_name = group_name.strip()
    first_word = first_word.strip().lower()

    if not first_word:
        logger.warning("Group creation rejected without an initial word")
        raise ValueError("Please enter at least one word for the group.")

    if not group_name:
        logger.warning("Attempted to create a group with an empty name")
        raise ValueError("Group name cannot be empty.")

    logger.info(f"Creating word group '{group_name}'")

    try:
        with get_database_service().transaction() as cursor:
            query_select_group_id_by_name(cursor, group_name)
            existing_group = cursor.fetchone()

            if existing_group is not None:
                logger.warning(f"Group creation rejected because group '{group_name}' already exists")
                raise ValueError(f"A group named '{group_name}' already exists.")

            query_select_word_id_by_text(cursor, first_word)
            first_word_row = cursor.fetchone()
            if first_word_row is None:
                logger.warning(f"Initial word '{first_word}' is not in the database", )
                raise ValueError(f"Word '{first_word}' does not exist in the database.")

            group_id_var = cursor.var(int)

            query_insert_group_returning_id(cursor, group_name=group_name, description=description, group_id=group_id_var)

            group_id = group_id_var.getvalue()[0]
            query_insert_group_word(cursor, group_id, int(first_word_row[0]))

        logger.info(f"Created word group '{group_name}' with id {group_id}")

        return group_id

    except ValueError:
        raise

    except Exception as e:
        logger.error(f"Failed to create group '{group_name}' due to '{e}'")
        raise


def add_word_to_group(group_id: int, word: str) -> None:
    """
    Add a word to a group, rejecting duplicate memberships.
    :param group_id: Target group identifier.
    :param word: Word to add.
    :return: None.
    """
    word = word.strip().lower()
    if not word:
        logger.warning(f"Empty word rejected for group id {group_id}")
        raise ValueError("Please enter a word.")

    logger.info(f"Adding word '{word}' to group {group_id}")
    try:
        with get_database_service().transaction() as cursor:
            query_select_word_id_by_text(cursor, word)
            row = cursor.fetchone()
            if row is None:
                logger.warning(f"Unknown word '{word}' for group {group_id}")
                raise ValueError(f"Word '{word}' does not exist in the database.")

            word_id = row[0]
            query_select_group_words(cursor, group_id)
            if any(group_word_id == word_id for group_word_id, _ in cursor.fetchall()):
                logger.warning(f"Duplicate word '{word}' in group {group_id}")
                raise ValueError(f"Word '{word}' is already in this group.")

            try:
                query_insert_group_word(cursor, group_id, word_id)
            except oracledb.IntegrityError as exc:
                # Also handle concurrent requests racing after the SELECT.
                if exc.args and getattr(exc.args[0], "code", None) == 1:
                    logger.warning(f"Oracle rejected duplicate word '{word}' for group {group_id}")
                    raise ValueError(f"Word '{word}' is already in this group.") from exc
                raise

        logger.info(f"Word '{word}' added to group {group_id}")
    except ValueError:
        raise
    except Exception:
        logger.error(f"Failed to add word '{word}' to group {group_id}")
        raise


def remove_word_from_group(group_id: int, word: str) -> bool:
    """
    Removes a word from a word group.
    :param group_id: The ID of the group.
    :param word: The word to remove.
    :return: True if the word was removed, False otherwise.
    """
    word = word.strip().lower()
    logger.info(f"Removing word '{word}' from group id {group_id}")

    try:
        with get_database_service().transaction() as cursor:
            query_select_group_words(cursor, group_id)
            current_words = cursor.fetchall()
            if len(current_words) <= 1 and any(current_word.lower() == word for _, current_word in current_words):
                logger.warning(f"Refusing to remove last word from group {group_id}")
                raise ValueError("A group must contain at least one word. Delete the group instead.")

            query_delete_group_word_by_text(cursor, group_id, word)
            removed = cursor.rowcount > 0

        if removed:
            logger.info(f"Removed word '{word}' from group id {group_id}")

        else:
            logger.warning(f"Word '{word}' was not found in group id {group_id}")

        return removed

    except Exception as e:
        logger.error(f"Failed to remove word '{word}' from group id {group_id} due to '{e}'")
        raise


def get_group_words(group_id: int) -> list[tuple[int, str]]:
    """
    Returns all words assigned to a word group.
    :param group_id: The ID of the group.
    :return: A list of tuples in the format:
        [
            (word_id, word_text),
            ...
        ]
    """
    logger.info(f'Fetching words for group id {group_id}')

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_group_words(cursor, group_id)
            result = cursor.fetchall()
            logger.info(f'Fetched {len(result)} words for group id {group_id}')
            return result

    except Exception as e:
        logger.error(f'Failed to fetch words for group id {group_id} due to {e}')
        raise


def get_groups() -> list[tuple[Any, ...]]:
    """
    Returns all word groups.
    :return:A list containing the stored word groups.
    """
    logger.info("Fetching all word groups")

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_groups(cursor)
            result = cursor.fetchall()
            logger.info(f'Fetched {len(result)} word groups')
            return result

    except Exception as e:
        logger.error(f"Failed to fetch word groups due to {e}")
        raise


def get_group_occurrences(group_id: int) -> list[tuple[Any, ...]]:
    """
    Returns all occurrences of words belonging to a word group.
    :param group_id: The ID of the group.
    :return: A list containing occurrences of the group's words.
    """
    logger.info(f'Fetching occurrences for group id {group_id}')

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_group_occurrences(cursor, group_id)
            result = cursor.fetchall()
            logger.info(f'Fetched {len(result)} occurrences for group id {group_id}')
            return result

    except Exception as e:
        logger.error(f'Failed to fetch occurrences for group id {group_id} due to {e}')
        raise


def update_group(group_id: int, group_name: str, description: str | None = None) -> bool:
    """
    Update group details while enforcing a case-insensitive unique name.
    :param group_id: ID of the group being edited.
    :param group_name: Proposed group name.
    :param description: Optional group description.
    :return: True if updated, False if the group no longer exists.
    """
    group_name = group_name.strip()
    if not group_name:
        logger.warning(f"Group update rejected: empty name for group id {group_id}")
        raise ValueError("Group name is required.")

    logger.info(f"Updating group id {group_id} to name '{group_name}'")
    try:
        with get_database_service().transaction() as cursor:
            query_select_group_id_by_name(cursor, group_name)
            existing_group = cursor.fetchone()
            if existing_group is not None and int(existing_group[0]) != group_id:
                logger.warning(f"Group name '{group_name}' is already used by group id {existing_group[0]}")
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
                    logger.warning(f"Oracle rejected duplicate name '{group_name}' for group {group_id}")
                    raise ValueError(f"A group named '{group_name}' already exists.")
                raise

            updated = cursor.rowcount > 0

        if updated:
            logger.info(f"Group id {group_id} updated successfully")
        else:
            logger.warning(f"Group id {group_id} was not found during update")
        return updated
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to update group id {group_id}")
        raise


def delete_group(group_id: int) -> bool:
    """
    Deletes a word group.
    Words themselves are not deleted. Only the group and its word associations are removed.
    :param group_id: The ID of the group to delete.
    :return: True if the group was deleted, False if it did not exist.
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

    except Exception as e:
        logger.error(f'Failed to delete group id {group_id} due to {e}')
        raise
