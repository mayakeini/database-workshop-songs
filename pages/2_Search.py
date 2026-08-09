import logging
from typing import Any

import streamlit as st

from src.logger_config import setup_logger
from src.search_service import (
    search_songs,
    search_word,
    get_context,
)

setup_logger()

logger = logging.getLogger(__name__)


def display_song_results(results: list[tuple[Any, ...]]) -> None:
    """
    Displays song metadata search results in a table.

    Args:
        results: Song rows returned from search_songs().

    Returns:
        None.
    """
    logger.info(
        "Displaying %s song search results",
        len(results),
    )

    if not results:
        logger.info("No songs matched the search")
        st.info("No songs found.")
        return

    rows = []

    for (
        song_id,
        title,
        artist,
        album,
        publication_year,
        upload_date,
    ) in results:
        rows.append(
            {
                "ID": song_id,
                "Title": title,
                "Artist": artist,
                "Album": album or "",
                "Publication Year": publication_year,
                "Upload Date": upload_date,
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )


def display_word_results(results: list[tuple[Any, ...]]) -> None:
    """
    Displays all occurrences of a searched word.

    Each occurrence includes its song, stanza, line positions,
    word position, and surrounding textual context.

    Args:
        results: Word occurrence rows returned from search_word().

    Returns:
        None.
    """
    logger.info(
        "Displaying %s word occurrences",
        len(results),
    )

    if not results:
        logger.info("No occurrences found for searched word")
        st.info("The word was not found.")
        return

    st.success(
        f"Found {len(results)} occurrence"
        f"{'s' if len(results) != 1 else ''}."
    )

    for index, result in enumerate(results, start=1):
        (
            occurrence_id,
            song_id,
            title,
            artist,
            stanza_number,
            global_line_number,
            line_number_in_stanza,
            position_in_line,
            position_in_song,
            original_token,
        ) = result

        with st.expander(
            f"{index}. {title} — line {global_line_number}"
        ):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.write(f"**Song:** {title}")
                st.write(f"**Artist:** {artist}")

            with col2:
                st.write(f"**Stanza:** {stanza_number}")
                st.write(
                    f"**Line in stanza:** "
                    f"{line_number_in_stanza}"
                )

            with col3:
                st.write(
                    f"**Position in line:** {position_in_line}"
                )
                st.write(
                    f"**Position in song:** {position_in_song}"
                )

            try:
                context = get_context(
                    song_id=song_id,
                    global_line_number=global_line_number,
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

            except Exception:
                logger.exception(
                    "Failed to load context for occurrence id %s",
                    occurrence_id,
                )

                st.error(
                    "Could not load the context for this occurrence."
                )


def render_song_search() -> None:
    """
    Renders the song metadata search interface.

    Users can search by title, artist, album, publication year,
    or any combination of these fields.

    Returns:
        None.
    """
    logger.info("Rendering song metadata search")

    st.subheader("Search Songs")

    with st.form("song_search_form"):
        title = st.text_input(
            "Song Title",
            key="search_song_title",
        )

        artist = st.text_input(
            "Artist",
            key="search_song_artist",
        )

        album = st.text_input(
            "Album",
            key="search_song_album",
        )

        use_year = st.checkbox(
            "Filter by publication year"
        )

        publication_year = st.number_input(
            "Publication Year",
            min_value=1000,
            max_value=9999,
            step=1,
            disabled=not use_year,
        )

        submitted = st.form_submit_button(
            "Search Songs"
        )

    if not submitted:
        return

    logger.info(
        "Song search submitted: title='%s', artist='%s', "
        "album='%s', year=%s",
        title,
        artist,
        album,
        publication_year if use_year else None,
    )

    try:
        results = search_songs(
            title=title.strip() or None,
            artist=artist.strip() or None,
            album=album.strip() or None,
            publication_year=(
                int(publication_year)
                if use_year
                else None
            ),
        )

        display_song_results(results)

    except Exception:
        logger.exception("Song search failed")

        st.error(
            "Could not search the songs. "
            "Please check the application logs."
        )


def render_word_search() -> None:
    """
    Renders the word search interface.

    Users can search for a normalized word and view all of its
    occurrences together with their locations and context.

    Returns:
        None.
    """
    logger.info("Rendering word search")

    st.subheader("Search Word")

    with st.form("word_search_form"):
        word = st.text_input(
            "Word *",
            key="search_word",
        )

        submitted = st.form_submit_button(
            "Search Word"
        )

    if not submitted:
        return

    word = word.strip()

    if not word:
        logger.warning(
            "Word search rejected because the input was empty"
        )

        st.error("Please enter a word.")
        return

    logger.info(
        "Searching for word '%s'",
        word,
    )

    try:
        results = search_word(word)

        display_word_results(results)

    except Exception:
        logger.exception(
            "Word search failed for '%s'",
            word,
        )

        st.error(
            "Could not search for the word. "
            "Please check the application logs."
        )


def main() -> None:
    """
    Renders the Search page of the concordance system.

    The page contains separate interfaces for metadata-based
    song search and word-occurrence search.

    Returns:
        None.
    """
    logger.info("Rendering search page")

    st.title("Search")

    song_tab, word_tab = st.tabs(
        [
            "Search Songs",
            "Search Word",
        ]
    )

    with song_tab:
        render_song_search()

    with word_tab:
        render_word_search()

    logger.info("Search page rendered successfully")


if __name__ == "__main__":
    main()