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
    get_group_occurrences
)
from src.logger_config import setup_logger

setup_logger()

logger = logging.getLogger(__name__)


def build_group_options(groups: list[tuple[Any, ...]]) -> dict[str, int]:
    """
    Converts database group rows into Streamlit selectbox options.
    :param groups: Group rows returned from get_groups().
    :return: A dictionary mapping a display label to a group ID.
    """
    logger.info(f'Building group selection options from {len(groups)} groups')
    options = {group_name: group_id for (group_id, group_name, description, creation_date) in groups}
    logger.info(f'Built {len(options)} group selection options')
    return options


def render_create_group() -> None:
    """
    Renders the interface for creating a new word group.
    Displays a persistent success message after creation and resets the form fields after a group is created successfully.
    :return: None
    """
    logger.info("Rendering create group section")
    st.subheader("Create Group")
    success_message = st.session_state.pop("create_group_success_message", None)

    if success_message:
        st.success(success_message)

    if "create_group_form_version" not in st.session_state:
        st.session_state["create_group_form_version"] = 0

    form_version = st.session_state["create_group_form_version"]

    with st.form(f"create_group_form_{form_version}",):
        group_name = st.text_input(
            "Group Name *",
            key=f"new_group_name_{form_version}",
        )

        description = st.text_area(
            "Description",
            key=f"new_group_description_{form_version}",
        )

        first_word = st.text_input(
            "First Word *",
            key=f"new_group_first_word_{form_version}",
            help="Choose a word that already occurs in an uploaded song.",
        )

        submitted = st.form_submit_button("Create Group",)

    if not submitted:
        return

    group_name = group_name.strip()
    description = description.strip()
    first_word = first_word.strip()

    if not first_word:
        st.error("Please enter at least one word for the group.")
        return

    if not group_name:
        logger.warning("Group creation rejected because the name is empty")
        st.error("Group name is required.")
        return

    try:
        group_id = create_group(
            group_name=group_name,
            description=description or None,
            first_word=first_word,
        )

        logger.info(f"Group '{group_name}' created successfully with id {group_id}")
        st.session_state["create_group_success_message"] = (f"Group '{group_name}' created successfully.")
        st.session_state["create_group_form_version"] += 1
        st.rerun()

    except ValueError as error:
        logger.warning(f"Could not create group '{group_name}': {error}")
        st.error(str(error))

    except Exception as e:
        logger.error(f"Unexpected error while creating group '{group_name}'. Error: {e}")
        st.error("Could not create the group due to an unexpected error. Please try again.")


def render_group_editor(group_id: int, group_name: str, description: str | None) -> None:
    """
    Renders controls for editing or deleting an existing group.
    :param group_id: ID of the selected group.
    :param group_name: Current group name.
    :param description: Current group description.
    :return: None.
    """
    logger.info(f'Rendering editor for group id {group_id}')
    st.subheader("Edit Group")

    with st.form(f"edit_group_form_{group_id}"):
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

        update_submitted = st.form_submit_button("Save Changes")

    if update_submitted:
        updated_name = updated_name.strip()
        updated_description = updated_description.strip()

        if not updated_name:
            logger.warning(f'Group update rejected for id {group_id}: empty name')
            st.error("Group name is required.")

        else:
            try:
                updated = update_group(
                    group_id=group_id,
                    group_name=updated_name,
                    description=updated_description or None,
                )

                if updated:
                    logger.info(f'Group id {group_id} updated successfully')
                    st.success("Group updated successfully.")
                    st.rerun()

                else:
                    logger.warning(f'Group id {group_id} was not found during update')
                    st.warning("The selected group no longer exists.")

            except ValueError as error:
                logger.warning(f"Group update rejected for id {group_id}: {error}")
                st.error(str(error))

            except Exception as e:
                logger.error(f"Unexpected group update error for id {group_id}: {e}")
                st.error("Could not update the group. Please try again.")

    st.markdown("---")
    st.warning("Deleting a group removes the group and its word associations, but does not delete the words "
               "from the database.")

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
                logger.info(f'Group id {group_id} deleted successfully')
                st.success("Group deleted successfully.")
                st.rerun()

            else:
                logger.warning(f'Group id {group_id} was not found during deletion')
                st.warning("The selected group no longer exists.")

        except Exception as error:
            logger.exception(f'Failed to delete group id {group_id} due to an unexpected error. Error: {error}')
            st.error(f"Could not delete the group: {error}")


def render_group_words(group_id: int) -> None:
    """
    Renders the words currently assigned to a group and controls for adding or removing words.
    :param group_id: ID of the selected group.
    :return: None.
    """
    logger.info(f'Rendering words for group id {group_id}')
    st.subheader("Words in Group")

    try:
        words = get_group_words(group_id)

    except Exception as e:
        logger.error(f'Failed to fetch words for group id {group_id} due to an unexpected error. Error: {e}')
        st.error("Could not load the group's words.")
        return

    if words:
        rows = [{"Word ID": word_id, "Word": text} for (word_id, text) in words]

        st.dataframe(rows, use_container_width=True, hide_index=True)

    else:
        st.info("This group does not contain any words yet.")

    st.markdown("### Add Word")

    message_key = f"add_word_success_{group_id}"
    success_message = st.session_state.pop(message_key, None)
    if success_message:
        st.success(success_message)

    version_key = f"add_word_form_version_{group_id}"
    if version_key not in st.session_state:
        st.session_state[version_key] = 0
    version = st.session_state[version_key]

    with st.form(f"add_word_form_{group_id}_{version}"):
        word_to_add = st.text_input("Word *", key=f"word_to_add_{group_id}_{version}")
        add_submitted = st.form_submit_button("Add Word")

    if add_submitted:
        word_to_add = word_to_add.strip()
        if not word_to_add:
            logger.warning("Empty word rejected for group %s", group_id)
            st.error("Please enter a word.")
        else:
            try:
                add_word_to_group(group_id=group_id, word=word_to_add)
                logger.info(f"Word '{word_to_add}' added to group {group_id}")
                st.session_state[message_key] = (f"Word '{word_to_add}' added successfully.")
                st.session_state[version_key] += 1
                st.rerun()
            except ValueError as exc:
                logger.warning(f"Word '{word_to_add}' rejected for group {group_id}: {exc}")
                st.error(str(exc))
            except Exception as e:
                logger.error(f"Unexpected error adding '{word_to_add}' to group {group_id}: {e}")
                st.error("Could not add the word. Please try again.")

    if words:
        st.markdown("### Remove Word")
        word_options = {text: word_id for (word_id, text) in words}

        selected_word = st.selectbox(
            "Select Word",
            options=list(word_options.keys()),
            key=f"remove_word_select_{group_id}"
        )

        if st.button("Remove Word", key=f"remove_word_button_{group_id}"):
            try:
                removed = remove_word_from_group(group_id=group_id, word=selected_word)

                if removed:
                    logger.info(f"Word '{selected_word}' removed from group id {group_id}")
                    st.success(f"Word '{selected_word}' removed successfully.")
                    st.rerun()

                else:
                    logger.warning(f"Word '{selected_word}' was not found in group id {group_id}")
                    st.warning("The selected word is no longer in the group.")

            except ValueError as error:
                logger.warning(f"Cannot remove word '{selected_word}' from group {group_id}: {error}")
                st.error(str(error))

            except Exception as e:
                logger.error(f"Failed to remove word '{selected_word}' from group id {group_id} due to an "
                             f"unexpected error. Error: {e}"
                )
                st.error("Could not remove the word. Please try again.")


def render_group_occurrences(group_id: int) -> None:
    """
    Renders all occurrences of words belonging to the selected group.
    :param group_id: ID of the selected group.
    :return: None.
    """
    logger.info(f'Rendering occurrences for group id {group_id}')
    st.subheader("Group Occurrences")

    try:
        occurrences = get_group_occurrences(group_id)

    except Exception as e:
        logger.error(f'Failed to fetch occurrences for group id {group_id} due to an unexpected error. Error: {e}')
        st.error("Could not load group occurrences.")
        return

    if not occurrences:
        logger.info(f'No occurrences found for group id {group_id}')
        st.info("No occurrences were found for this group.")
        return

    rows = []

    for (word,
         song_id,
         song_title,
         stanza_number,
         global_line_number,
         line_number_in_stanza,
         position_in_line,
         original_token) in occurrences:
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

    st.caption(f"{len(rows)} occurrence{'s' if len(rows) != 1 else ''}")
    st.dataframe(rows, use_container_width=True, hide_index=True)
    logger.info(f'Displayed {len(rows)} occurrences for group id {group_id}')


def main() -> None:
    """
    Renders the Word Groups management page.
    The page allows users to create groups, edit or delete existing groups, add or remove words,
    and inspect all occurrences of words belonging to a group.
    :return: None.
    """
    logger.info("Rendering word groups page")
    st.title("Word Groups")
    st.write("Create custom groups of words and inspect their occurrences across the song collection.")

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

        except Exception as e:
            logger.error(f"Failed to load word groups due to an unexpected error. Error: {e}")
            st.error("Could not load the word groups.")
            return

        if not groups:
            st.info("No word groups have been created yet.")
            return

        group_options = build_group_options(groups)
        selected_group_name = st.selectbox("Select Group", options=list(group_options.keys()))
        selected_group_id = group_options[selected_group_name]
        selected_group = next(group for group in groups if group[0] == selected_group_id)
        (group_id, group_name, description, creation_date) = selected_group
        st.caption(f"Created: {creation_date}")
        editor_tab, words_tab, occurrences_tab = st.tabs(
            [
                "Group Details",
                "Words",
                "Occurrences",
            ]
        )

        with editor_tab:
            render_group_editor(group_id=group_id, group_name=group_name, description=description)

        with words_tab:
            render_group_words(group_id=group_id)

        with occurrences_tab:
            render_group_occurrences(group_id=group_id)

    logger.info("Word groups page rendered successfully")


if __name__ == "__main__":
    main()
