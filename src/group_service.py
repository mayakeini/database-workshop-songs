import logging

from src.db import get_connection

logger = logging.getLogger(__name__)


def create_group(group_name, description=None):
    connection = get_connection()

    try:
        cursor = connection.cursor()

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

    except Exception:
        connection.rollback()
        logger.exception("Failed to create group '%s'", group_name)
        raise

    finally:
        connection.close()

def add_word_to_group(group_id, word):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT word_id
            FROM words
            WHERE text = LOWER(:word)
            """,
            word=word,
        )

        row = cursor.fetchone()

        if row is None:
            raise ValueError(f"Word '{word}' does not exist in database")

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
            "Added word '%s' to group %s",
            word,
            group_id,
        )

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to add word '%s' to group %s",
            word,
            group_id,
        )
        raise

    finally:
        connection.close()

def remove_word_from_group(group_id, word):
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
                    WHERE text = LOWER(:word)
              )
            """,
            group_id=group_id,
            word=word,
        )

        connection.commit()

        return cursor.rowcount > 0

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to remove word '%s' from group %s",
            word,
            group_id,
        )
        raise

    finally:
        connection.close()

def get_group_words(group_id):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                w.word_id,
                w.text,
                w.word_length
            FROM group_words gw
            JOIN words w
                ON gw.word_id = w.word_id
            WHERE gw.group_id = :group_id
            ORDER BY w.text
            """,
            group_id=group_id,
        )

        return cursor.fetchall()

    finally:
        connection.close()

def get_groups():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                group_id,
                group_name,
                description,
                creation_date
            FROM word_groups
            ORDER BY group_name
            """
        )

        return cursor.fetchall()

    finally:
        connection.close()

def get_group_occurrences(group_id):
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

        return cursor.fetchall()

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
    if not group_name.strip():
        logger.warning(
            "Attempted to update group id %s with an empty name",
            group_id,
        )
        raise ValueError("Group name cannot be empty")

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
            SET group_name = :group_name,
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


def delete_group(group_id: int) -> bool:
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