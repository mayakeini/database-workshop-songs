import logging
from datetime import datetime

import streamlit as st

from src.logger_config import setup_logger
from src.xml_service import (
    export_database_to_xml,
    restore_database_from_xml,
)

setup_logger()

logger = logging.getLogger(__name__)


def render_backup() -> None:
    """
    Renders the database XML backup interface.

    Users can generate a complete XML backup and download it
    to their computer.

    Returns:
        None.
    """
    logger.info(
        "Rendering XML backup section"
    )

    st.subheader("Backup Database")

    st.write(
        "Export all project data to a single XML backup file."
    )

    if "xml_backup_data" not in st.session_state:
        st.session_state.xml_backup_data = None

    if "xml_backup_filename" not in st.session_state:
        st.session_state.xml_backup_filename = None

    if st.button(
        "Generate XML Backup",
        key="generate_xml_backup",
    ):
        logger.info(
            "XML backup requested by user"
        )

        try:
            xml_data = export_database_to_xml()

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            st.session_state.xml_backup_data = xml_data
            st.session_state.xml_backup_filename = (
                f"concordance_backup_{timestamp}.xml"
            )

            logger.info(
                "XML backup generated successfully"
            )

            st.success(
                "Backup generated successfully."
            )

        except Exception:
            logger.exception(
                "Failed to generate XML backup"
            )

            st.error(
                "Could not generate the XML backup."
            )

    if st.session_state.xml_backup_data is not None:
        st.download_button(
            label="Download XML Backup",
            data=st.session_state.xml_backup_data,
            file_name=st.session_state.xml_backup_filename,
            mime="application/xml",
            width="stretch",
        )


def render_restore() -> None:
    """
    Renders the XML database restoration interface.

    Restoring replaces all current project data with the contents
    of the uploaded XML backup.

    Returns:
        None.
    """
    logger.info(
        "Rendering XML restore section"
    )

    st.subheader("Restore Database")

    st.error(
        "Restoring a backup replaces all current project data."
    )

    uploaded_file = st.file_uploader(
        "XML Backup File *",
        type=["xml"],
        key="restore_xml_file",
    )

    confirm_restore = st.checkbox(
        "I understand that the current data will be replaced.",
        key="confirm_xml_restore",
    )

    restore_clicked = st.button(
        "Restore Database",
        disabled=(
            uploaded_file is None
            or not confirm_restore
        ),
        key="restore_database_button",
    )

    if not restore_clicked:
        return

    logger.info(f"Database restore requested using file '{uploaded_file.name}'")

    try:
        xml_data = uploaded_file.getvalue()

        counts = restore_database_from_xml(
            xml_data=xml_data,
        )

        logger.info(
            "Database restored successfully"
        )

        st.success(
            "Database restored successfully."
        )

        st.subheader("Restored Records")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Songs",
                counts["songs"],
            )

        with col2:
            st.metric(
                "Stanzas",
                counts["stanzas"],
            )

        with col3:
            st.metric(
                "Unique Words",
                counts["words"],
            )

        with col4:
            st.metric(
                "Word Occurrences",
                counts["word_occurrences"],
            )

        col5, col6, col7 = st.columns(3)

        with col5:
            st.metric(
                "Word Groups",
                counts["word_groups"],
            )

        with col6:
            st.metric(
                "Phrases",
                counts["phrases"],
            )

        with col7:
            st.metric(
                "Phrase Occurrences",
                counts["phrase_occurrences"],
            )

    except ValueError as error:
        logger.warning(f'XML restore rejected: {error}')

        st.error(str(error))

    except Exception:
        logger.exception(
            "Failed to restore database from XML"
        )

        st.error(
            "Could not restore the database. "
            "The existing data was not changed."
        )


def main() -> None:
    """
    Renders the Backup & Restore page.

    The page provides complete XML export and restoration
    functionality for the concordance database.

    Returns:
        None.
    """
    logger.info(
        "Rendering backup and restore page"
    )

    st.title("Backup & Restore")

    st.write(
        "Create a complete XML backup of the concordance database "
        "or restore the system from a previously generated backup."
    )

    backup_tab, restore_tab = st.tabs(
        [
            "Backup",
            "Restore",
        ]
    )

    with backup_tab:
        render_backup()

    with restore_tab:
        render_restore()

    logger.info(
        "Backup and restore page rendered successfully"
    )


if __name__ == "__main__":
    main()