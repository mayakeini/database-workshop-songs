import logging

import streamlit as st

from src.logger_config import setup_logger
from src.statistics_service import get_database_summary

setup_logger()

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Renders the main page of the concordance application.
    The page displays a short description of the system and general statistics about the current database.
    :return: None.
    """
    logger.info("Rendering main application page")
    st.set_page_config(
        page_title="Songs Concordance System",
        page_icon="🎵",
        layout="wide"
    )

    st.title("🎵 Songs Concordance System")

    st.write(
        """
        A concordance and text retrieval system for English songs.

        The system allows users to upload songs, search for words and
        phrases, inspect word locations and contexts, create word groups,
        view indexes and statistics, and back up or restore the database.
        """
    )

    try:
        summary = get_database_summary()
        st.subheader("Database Summary")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Songs", summary["song_count"])

        with col2:
            st.metric("Total Words", summary["total_words"])

        with col3:
            st.metric("Unique Words", summary["unique_words"])

        with col4:
            st.metric("Average Word Length", summary["average_word_length"])

        logger.info("Main page rendered successfully")

    except Exception as e:
        logger.error(f"Failed to load database summary on main page due to {e}")
        st.error("Could not load database statistics. Please verify that Oracle is running.")


if __name__ == "__main__":
    main()
