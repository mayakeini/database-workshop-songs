import logging
from typing import Any

import streamlit as st

from src.logger_config import setup_logger
from src.phrase_service import (
    create_and_search_phrase,
    get_phrases,
    get_phrase_occurrences_with_context,
    delete_phrase,
)

setup_logger()

logger = logging.getLogger(__name__)


def build_phrase_options(
    phrases: list[tuple[Any, ...]],
) -> dict[str, int]:
    """
    Converts phrase rows into Streamlit selectbox options.

    Args:
        phrases: Phrase rows returned from get_phrases().

    Returns:
        A dictionary mapping a display label to a phrase ID.
    """
    logger.info(f'Building phrase selection options from {len(phrases)} phrases')

    options = {
        f"{phrase_name} — {phrase_text}": phrase_id
        for (
            phrase_id,
            phrase_name,
            phrase_text,
            creation_date,
        ) in phrases
    }

    logger.info(f'Built {len(options)} phrase selection options')

    return options


def render_create_phrase() -> None:
    """
    Renders the phrase creation form.

    The user provides a unique phrase name and a phrase text.
    After creation, the system searches all songs and stores
    the detected phrase occurrences.

    Returns:
        None.
    """
    logger.info("Rendering create phrase section")

    st.subheader("Create Phrase")

    st.write(
        "Define a sequence of words and search for all of its "
        "occurrences in the song collection."
    )

    st.caption("* Required fields")

    with st.form("create_phrase_form"):
        phrase_name = st.text_input(
            "Phrase Name *",
            key="new_phrase_name",
        )

        phrase_text = st.text_input(
            "Phrase Text *",
            key="new_phrase_text",
            placeholder="Example: love is",
        )

        submitted = st.form_submit_button(
            "Create and Search Phrase"
        )

    if not submitted:
        return

    phrase_name = phrase_name.strip()
    phrase_text = phrase_text.strip()

    if not phrase_name:
        logger.warning(
            "Phrase creation rejected because the phrase name is empty"
        )
        st.error("Phrase name is required.")
        return

    if not phrase_text:
        logger.warning(
            "Phrase creation rejected because the phrase text is empty"
        )
        st.error("Phrase text is required.")
        return

    logger.info(
        f"Phrase creation submitted: name='{phrase_name}', text='{phrase_text}'",
    )

    try:
        phrase_id = create_and_search_phrase(
            phrase_name=phrase_name,
            phrase_text=phrase_text,
        )

        logger.info(f"Phrase '{phrase_name}' created successfully with id {phrase_id}")

        st.success(
            f"Phrase '{phrase_name}' created successfully."
        )

        st.rerun()

    except Exception as error:
        logger.exception(f"Failed to create phrase '{phrase_name}'")

        st.error(
            f"Could not create the phrase: {error}"
        )


def render_phrase_details(
    phrase_id: int,
    phrase_name: str,
    phrase_text: str,
    creation_date: Any,
) -> None:
    """
    Renders the basic details of a selected phrase.

    Args:
        phrase_id: The database ID of the phrase.
        phrase_name: The display name of the phrase.
        phrase_text: The textual content of the phrase.
        creation_date: The phrase creation date returned from Oracle.

    Returns:
        None.
    """
    logger.info(f'Rendering details for phrase id {phrase_id}')

    st.subheader("Phrase Details")

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Name:** {phrase_name}")
        st.write(f"**Text:** {phrase_text}")

    with col2:
        st.write(f"**Phrase ID:** {phrase_id}")
        st.write(f"**Created:** {creation_date}")


def render_phrase_occurrences(
    phrase_id: int,
) -> None:
    """
    Renders all stored occurrences of a phrase together with
    their surrounding textual context.

    Args:
        phrase_id: The database ID of the phrase.

    Returns:
        None.
    """
    logger.info(f'Rendering occurrences for phrase id {phrase_id}')

    st.subheader("Phrase Occurrences")

    try:
        occurrences = get_phrase_occurrences_with_context(
            phrase_id=phrase_id,
        )

    except Exception:
        logger.exception(f'Failed to load occurrences for phrase id {phrase_id}')

        st.error(
            "Could not load phrase occurrences."
        )
        return

    if not occurrences:
        logger.info(f'No occurrences found for phrase id {phrase_id}')

        st.info(
            "No occurrences were found for this phrase."
        )
        return

    st.success(
        f"Found {len(occurrences)} occurrence"
        f"{'s' if len(occurrences) != 1 else ''}."
    )

    for index, occurrence in enumerate(
        occurrences,
        start=1,
    ):
        song_title = occurrence["song_title"]
        global_line_number = occurrence[
            "global_line_number"
        ]
        start_position = occurrence["start_position"]
        end_position = occurrence["end_position"]
        context = occurrence["context"]

        with st.expander(
            f"{index}. {song_title} — line {global_line_number}"
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.write(
                    f"**Song:** {song_title}"
                )
                st.write(
                    f"**Global Line:** {global_line_number}"
                )

            with col2:
                st.write(
                    f"**Start Position:** {start_position}"
                )
                st.write(
                    f"**End Position:** {end_position}"
                )

            st.markdown("**Context:**")

            for line_number, text in context.items():
                if line_number == global_line_number:
                    st.markdown(
                        f"➡️ **Line {line_number}: {text}**"
                    )
                else:
                    st.write(
                        f"Line {line_number}: {text}"
                    )

    logger.info(f'Displayed {len(occurrences)} occurrences for phrase id {phrase_id}')


def render_delete_phrase(
    phrase_id: int,
    phrase_name: str,
) -> None:
    """
    Renders controls for deleting a selected phrase.

    Args:
        phrase_id: The database ID of the phrase.
        phrase_name: The display name of the phrase.

    Returns:
        None.
    """
    logger.info(f'Rendering delete controls for phrase id {phrase_id}')

    st.subheader("Delete Phrase")

    st.warning(
        "Deleting a phrase also removes all stored occurrences "
        "of that phrase."
    )

    confirm_delete = st.checkbox(
        f"I understand and want to delete '{phrase_name}'",
        key=f"confirm_delete_phrase_{phrase_id}",
    )

    delete_clicked = st.button(
        "Delete Phrase",
        disabled=not confirm_delete,
        key=f"delete_phrase_{phrase_id}",
    )

    if not delete_clicked:
        return

    logger.info(f'Delete requested for phrase id {phrase_id}')

    try:
        deleted = delete_phrase(
            phrase_id=phrase_id,
        )

        if deleted:
            logger.info(f'Phrase id {phrase_id} deleted successfully')

            st.success(
                f"Phrase '{phrase_name}' deleted successfully."
            )

            st.rerun()

        else:
            logger.warning(f'Phrase id {phrase_id} was not found during deletion')

            st.warning(
                "The selected phrase no longer exists."
            )

    except Exception as error:
        logger.exception(f'Failed to delete phrase id {phrase_id}')

        st.error(
            f"Could not delete the phrase: {error}"
        )


def render_manage_phrases() -> None:
    """
    Renders the phrase management interface.

    Users can select an existing phrase, inspect its details,
    view all stored occurrences with context, and delete it.

    Returns:
        None.
    """
    logger.info("Rendering phrase management section")

    try:
        phrases = get_phrases()

    except Exception:
        logger.exception(
            "Failed to load phrases"
        )

        st.error(
            "Could not load the phrases."
        )
        return

    if not phrases:
        logger.info(
            "No phrases are currently defined"
        )

        st.info(
            "No phrases have been created yet."
        )
        return

    phrase_options = build_phrase_options(
        phrases=phrases,
    )

    selected_label = st.selectbox(
        "Select Phrase",
        options=list(phrase_options.keys()),
    )

    selected_phrase_id = phrase_options[
        selected_label
    ]

    selected_phrase = next(
        phrase
        for phrase in phrases
        if phrase[0] == selected_phrase_id
    )

    (
        phrase_id,
        phrase_name,
        phrase_text,
        creation_date,
    ) = selected_phrase

    details_tab, occurrences_tab, delete_tab = st.tabs(
        [
            "Details",
            "Occurrences",
            "Delete",
        ]
    )

    with details_tab:
        render_phrase_details(
            phrase_id=phrase_id,
            phrase_name=phrase_name,
            phrase_text=phrase_text,
            creation_date=creation_date,
        )

    with occurrences_tab:
        render_phrase_occurrences(
            phrase_id=phrase_id,
        )

    with delete_tab:
        render_delete_phrase(
            phrase_id=phrase_id,
            phrase_name=phrase_name,
        )


def main() -> None:
    """
    Renders the Phrases page.

    The page allows users to define linguistic phrases,
    search and store their occurrences, inspect their context,
    and manage existing phrase definitions.

    Returns:
        None.
    """
    logger.info("Rendering phrases page")

    st.title("Phrases")

    st.write(
        "Define sequences of words and find their occurrences "
        "inside the loaded songs."
    )

    create_tab, manage_tab = st.tabs(
        [
            "Create Phrase",
            "Manage Phrases",
        ]
    )

    with create_tab:
        render_create_phrase()

    with manage_tab:
        render_manage_phrases()

    logger.info(
        "Phrases page rendered successfully"
    )


if __name__ == "__main__":
    main()