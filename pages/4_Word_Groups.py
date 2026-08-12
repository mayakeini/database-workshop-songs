import logging
from typing import Any

import streamlit as st

from src.group_service import (
    create_group,
    update_group,
    delete_group,
    add_word_to_group,
    remove_word_from_group,
    get_groups,
    get_group_words,
    get_group_occurrences,
)
from src.logger_config import setup_logger

setup_logger()

logger = logging.getLogger(__name__)


def build_group_options(
    groups: list[tuple[Any, ...]],
) -> dict[str, int]:
    """
    Converts database group rows into Streamlit selectbox options.

    Args:
        groups: Group rows returned from get_groups().

    Returns:
        A dictionary mapping a display label to a group ID.
    """
    logger.info(
        "Building group selection options from %s groups",
        len(groups),
    )

    options = {
        group_name: group_id
        for (
            group_id,
            group_name,
            description,
            creation_date,
        ) in groups
    }

    logger.info(
        "Built %s group selection options",
        len(options),
    )

    return options


def render_create_group() -> None:
    """
    Renders the interface for creating a new word group.

    Returns:
        None.
    """
    logger.info("Rendering create group section")

    st.subheader("Create Group")

    with st.form("create_group_form"):
        group_name = st.text_input(
            "Group Name *",
            key="new_group_name",
        )

        description = st.text_area(
            "Description",
            key="new_group_description",
        )

        submitted = st.form_submit_button(
            "Create Group"
        )

    if not submitted:
        return

    group_name = group_name.strip()
    description = description.strip()

    if not group_name:
        logger.warning(
            "Group creation rejected because the name is empty"
        )

        st.error("Group name is required.")
        return

    try:
        group_id = create_group(
            group_name=group_name,
            description=description or None,
        )

        logger.info(
            "Group '%s' created successfully with id %s",
            group_name,
            group_id,
        )

        st.success(
            f"Group '{group_name}' created successfully."
        )

        st.rerun()

    except Exception as error:
        logger.exception(
            "Failed to create group '%s'",
            group_name,
        )

        st.error(
            f"Could not create the group: {error}"
        )


def render_group_editor(
    group_id: int,
    group_name: str,
    description: str | None,
) -> None:
    """
    Renders controls for editing or deleting an existing group.

    Args:
        group_id: ID of the selected group.
        group_name: Current group name.
        description: Current group description.

    Returns:
        None.
    """
    logger.info(
        "Rendering editor for group id %s",
        group_id,
    )

    st.subheader("Edit Group")

    with st.form(
        f"edit_group_form_{group_id}"
    ):
        updated_name = st.text_input(
            "Group Name *",
            value=group_name,
            key=f"edit_group_name_{group_id}",
        )

        updated_description = st.text_area(
            "Description",
            value=description or "",
            key=f"edit_group_description_{group_id}",
        )

        update_submitted = st.form_submit_button(
            "Save Changes"
        )

    if update_submitted:
        updated_name = updated_name.strip()
        updated_description = updated_description.strip()

        if not updated_name:
            logger.warning(
                "Group update rejected for id %s: empty name",
                group_id,
            )

            st.error("Group name is required.")

        else:
            try:
                updated = update_group(
                    group_id=group_id,
                    group_name=updated_name,
                    description=updated_description or None,
                )

                if updated:
                    logger.info(
                        "Group id %s updated successfully",
                        group_id,
                    )

                    st.success(
                        "Group updated successfully."
                    )

                    st.rerun()

                else:
                    logger.warning(
                        "Group id %s was not found during update",
                        group_id,
                    )

                    st.warning(
                        "The selected group no longer exists."
                    )

            except Exception as error:
                logger.exception(
                    "Failed to update group id %s",
                    group_id,
                )

                st.error(
                    f"Could not update the group: {error}"
                )

    st.markdown("---")

    st.warning(
        "Deleting a group removes the group and its word associations, "
        "but does not delete the words from the database."
    )

    confirm_delete = st.checkbox(
        "I understand and want to delete this group",
        key=f"confirm_delete_group_{group_id}",
    )

    if st.button(
        "Delete Group",
        disabled=not confirm_delete,
        key=f"delete_group_{group_id}",
    ):
        try:
            deleted = delete_group(group_id)

            if deleted:
                logger.info(
                    "Group id %s deleted successfully",
                    group_id,
                )

                st.success(
                    "Group deleted successfully."
                )

                st.rerun()

            else:
                logger.warning(
                    "Group id %s was not found during deletion",
                    group_id,
                )

                st.warning(
                    "The selected group no longer exists."
                )

        except Exception as error:
            logger.exception(
                "Failed to delete group id %s",
                group_id,
            )

            st.error(
                f"Could not delete the group: {error}"
            )


def render_group_words(
    group_id: int,
) -> None:
    """
    Renders the words currently assigned to a group and controls
    for adding or removing words.

    Args:
        group_id: ID of the selected group.

    Returns:
        None.
    """
    logger.info(
        "Rendering words for group id %s",
        group_id,
    )

    st.subheader("Words in Group")

    try:
        words = get_group_words(
            group_id
        )

    except Exception:
        logger.exception(
            "Failed to fetch words for group id %s",
            group_id,
        )

        st.error(
            "Could not load the group's words."
        )
        return

    if words:
        rows = [
            {
                "Word ID": word_id,
                "Word": text,
            }
            for (
                word_id,
                text,
            ) in words
        ]

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info(
            "This group does not contain any words yet."
        )

    st.markdown("### Add Word")

    with st.form(
        f"add_word_form_{group_id}"
    ):
        word_to_add = st.text_input(
            "Word *",
            key=f"word_to_add_{group_id}",
        )

        add_submitted = st.form_submit_button(
            "Add Word"
        )

    if add_submitted:
        word_to_add = word_to_add.strip()

        if not word_to_add:
            logger.warning(
                "Add-word rejected for group id %s: empty word",
                group_id,
            )

            st.error(
                "Please enter a word."
            )

        else:
            try:
                add_word_to_group(
                    group_id=group_id,
                    word=word_to_add,
                )

                logger.info(
                    "Word '%s' added to group id %s",
                    word_to_add,
                    group_id,
                )

                st.success(
                    f"Word '{word_to_add}' added successfully."
                )

                st.rerun()

            except Exception as error:
                logger.exception(
                    "Failed to add word '%s' to group id %s",
                    word_to_add,
                    group_id,
                )

                st.error(
                    f"Could not add the word: {error}"
                )

    if words:
        st.markdown("### Remove Word")

        word_options = {
            text: word_id
            for (
                word_id,
                text,
            ) in words
        }

        selected_word = st.selectbox(
            "Select Word",
            options=list(
                word_options.keys()
            ),
            key=f"remove_word_select_{group_id}",
        )

        if st.button(
            "Remove Word",
            key=f"remove_word_button_{group_id}",
        ):
            try:
                removed = remove_word_from_group(
                    group_id=group_id,
                    word=selected_word,
                )

                if removed:
                    logger.info(
                        "Word '%s' removed from group id %s",
                        selected_word,
                        group_id,
                    )

                    st.success(
                        f"Word '{selected_word}' removed successfully."
                    )

                    st.rerun()

                else:
                    logger.warning(
                        "Word '%s' was not found in group id %s",
                        selected_word,
                        group_id,
                    )

                    st.warning(
                        "The selected word is no longer in the group."
                    )

            except Exception as error:
                logger.exception(
                    "Failed to remove word '%s' from group id %s",
                    selected_word,
                    group_id,
                )

                st.error(
                    f"Could not remove the word: {error}"
                )


def render_group_occurrences(
    group_id: int,
) -> None:
    """
    Renders all occurrences of words belonging to the selected group.

    Args:
        group_id: ID of the selected group.

    Returns:
        None.
    """
    logger.info(
        "Rendering occurrences for group id %s",
        group_id,
    )

    st.subheader("Group Occurrences")

    try:
        occurrences = get_group_occurrences(group_id)

    except Exception:
        logger.exception(
            "Failed to fetch occurrences for group id %s",
            group_id,
        )

        st.error(
            "Could not load group occurrences."
        )
        return

    if not occurrences:
        logger.info(
            "No occurrences found for group id %s",
            group_id,
        )

        st.info(
            "No occurrences were found for this group."
        )
        return

    rows = []

    for (
        word,
        song_id,
        song_title,
        stanza_number,
        global_line_number,
        line_number_in_stanza,
        position_in_line,
        original_token,
    ) in occurrences:
        rows.append(
            {
                "Word": word,
                "Song": song_title,
                "Stanza": stanza_number,
                "Global Line": global_line_number,
                "Line in Stanza": line_number_in_stanza,
                "Position in Line": position_in_line,
                "Original Token": original_token,
            }
        )

    st.caption(
        f"{len(rows)} occurrence"
        f"{'s' if len(rows) != 1 else ''}"
    )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )

    logger.info(
        "Displayed %s occurrences for group id %s",
        len(rows),
        group_id,
    )


def main() -> None:
    """
    Renders the Word Groups management page.

    The page allows users to create groups, edit or delete existing
    groups, add or remove words, and inspect all occurrences of words
    belonging to a group.

    Returns:
        None.
    """
    logger.info("Rendering word groups page")

    st.title("Word Groups")

    st.write(
        "Create custom groups of words and inspect their occurrences "
        "across the song collection."
    )

    create_tab, manage_tab = st.tabs(
        [
            "Create Group",
            "Manage Groups",
        ]
    )

    with create_tab:
        render_create_group()

    with manage_tab:
        try:
            groups = get_groups()

        except Exception:
            logger.exception(
                "Failed to load word groups"
            )

            st.error(
                "Could not load the word groups."
            )
            return

        if not groups:
            st.info(
                "No word groups have been created yet."
            )
            return

        group_options = build_group_options(groups)

        selected_group_name = st.selectbox(
            "Select Group",
            options=list(group_options.keys()),
        )

        selected_group_id = group_options[
            selected_group_name
        ]

        selected_group = next(
            group
            for group in groups
            if group[0] == selected_group_id
        )

        (
            group_id,
            group_name,
            description,
            creation_date,
        ) = selected_group

        st.caption(
            f"Created: {creation_date}"
        )

        editor_tab, words_tab, occurrences_tab = st.tabs(
            [
                "Group Details",
                "Words",
                "Occurrences",
            ]
        )

        with editor_tab:
            render_group_editor(
                group_id=group_id,
                group_name=group_name,
                description=description,
            )

        with words_tab:
            render_group_words(
                group_id=group_id,
            )

        with occurrences_tab:
            render_group_occurrences(
                group_id=group_id,
            )

    logger.info(
        "Word groups page rendered successfully"
    )


if __name__ == "__main__":
    main()