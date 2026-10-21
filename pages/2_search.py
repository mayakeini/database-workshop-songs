import logging
from typing import Any

from datetime import datetime

import streamlit as st

from src.logger_config import setup_logger
from src.search_service import (
    search_songs,
    search_word,
    get_context,
    find_line_by_global_number,
    find_line_by_stanza_position,
    find_word_by_position,
)
from src.song_service import get_song_text

setup_logger()

logger = logging.getLogger(__name__)


def format_upload_date(upload_date: Any) -> str:
    """
    Formats a stored upload date for display without its timezone.
    :param upload_date: Upload date returned from Oracle.
    :return: A display string containing date and time only.
    """
    logger.info(f"Formatting upload date: {upload_date}")
    return upload_date.rsplit(" ", maxsplit=1)[0]


def display_song_results(results: list[tuple[Any, ...]]) -> None:
    """
    Displays song metadata search results.
    Each matching song is displayed inside an expandable section containing its metadata and the reconstructed full
    song text.
    :param results: Song rows returned from search_songs().
    :return: None
    """
    logger.info(f'Displaying {len(results)} song search results')
    if not results:
        logger.info("No songs matched the search")
        st.info("No songs found.")
        return

    st.success(f"Found {len(results)} song{'s' if len(results) != 1 else ''}.")

    for index, result in enumerate(results, start=1):
        (song_id,
        title,
        artist,
        album,
        publication_year,
        upload_date) = result

        with st.expander(f"{index}. {title} — {artist}"):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Title:** {title}")
                st.write(f"**Artist:** {artist}")
                st.write(f"**Album:** {album or '—'}")

            with col2:
                st.write(f"**Publication Year:** {publication_year}")
                st.write(f"**Upload Date:** {format_upload_date(upload_date)}")
                st.write(f"**Song ID:** {song_id}")

            st.markdown("---")
            st.markdown("**Full Song:**")

            try:
                full_song = get_song_text(song_id=song_id)

                if full_song.strip():
                    st.text(full_song)
                    logger.info(f'Displayed full text for song id {song_id}')
                else:
                    logger.warning(f'Song id {song_id} has no reconstructed text')
                    st.info("No song text is available.")

            except Exception as e:
                logger.error(f'Failed to display full text for song id {song_id} due to {e}')
                st.error("Could not load the full song text.")

def display_word_results(results: list[tuple[Any, ...]]) -> None:
    """
    Display one word occurrence with Previous / Next navigation.
    :param results: Cached word occurrence rows from search_word().
    :return: None
    """
    logger.info(f"Displaying word occurrence navigator ({len(results)} results)")

    if not results:
        logger.info("The word was not found.")
        st.info("The word was not found.")
        return

    current_index = st.session_state.get("word_occurrence_index", 0)
    current_index = max(0, min(current_index, len(results) - 1))
    st.session_state["word_occurrence_index"] = current_index

    st.success(f"Found {len(results)} occurrence{'s' if len(results) != 1 else ''}.")
    st.caption(f"Occurrence {current_index + 1} of {len(results)}")

    (occurrence_id,
    song_id,
    title,
    artist,
    stanza_number,
    global_line_number,
    line_number_in_stanza,
    position_in_line,
    position_in_song,
    original_token) = results[current_index]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write(f"**Song:** {title}")
        st.write(f"**Artist:** {artist}")

    with col2:
        st.write(f"**Stanza:** {stanza_number}")
        st.write(f"**Global line:** {global_line_number}")
        st.write(f"**Line in stanza:** {line_number_in_stanza}")

    with col3:
        st.write(f"**Position in line:** {position_in_line}")
        st.write(f"**Position in song:** {position_in_song}")
        st.write(f"**Original token:** {original_token}")

    try:
        context = get_context(song_id=song_id, global_line_number=global_line_number)
        st.markdown("**Context:**")
        for line_number, text in context.items():
            if line_number == global_line_number:
                st.markdown(f"➡️ **Line {line_number}: {text}**")
            else:
                st.write(f"Line {line_number}: {text}")
    except Exception as e:
        logger.error(f"Failed to load context for occurrence id {occurrence_id} due to {e}")
        st.error("Could not load the context for this occurrence.")

    previous_col, next_col = st.columns(2)
    with previous_col:
        if st.button("◀ Previous", key="word_occurrence_previous", disabled=current_index == 0):
            st.session_state["word_occurrence_index"] = current_index - 1
            st.rerun()

    with next_col:
        if st.button("Next ▶", key="word_occurrence_next", disabled=current_index == len(results) - 1):
            st.session_state["word_occurrence_index"] = current_index + 1
            st.rerun()


def render_song_search() -> None:
    """
    Renders the song metadata search interface.
    Users can search by title, artist, album, publication year, or any combination of these fields.
    :return: None
    """
    logger.info("Rendering song metadata search")
    st.subheader("Search Songs")
    current_year = datetime.now().year
    use_year = st.checkbox("Filter by publication year", key="search_use_year")
    publication_year = st.number_input(
        "Publication Year",
        min_value=1000,
        max_value=current_year,
        value=current_year,
        step=1,
        disabled=not use_year,
        key="search_publication_year"
    )

    with st.form("song_search_form"):
        title = st.text_input("Song Title", key="search_song_title")
        artist = st.text_input("Artist", key="search_song_artist")
        album = st.text_input("Album", key="search_song_album")
        submitted = st.form_submit_button("Search Songs")

    if not submitted:
        return

    logger.info(f"Song search submitted: title='{title}', artist='{artist}', album='{album}', "
                f"year={publication_year if use_year else None}")

    try:
        results = search_songs(
            title=title.strip() or None,
            artist=artist.strip() or None,
            album=album.strip() or None,
            publication_year=(int(publication_year) if use_year else None)
        )

        display_song_results(results)

    except Exception as e:
        logger.error(f"Song search failed due to {e}")
        st.error("Could not search the songs. Please check the application logs.")

def render_word_search() -> None:
    """
    Render word search and persistent occurrence navigation.
    New searches replace cached results and reset navigation to the first occurrence.
    Navigating does not repeat the word search query.
    :return: None
    """
    logger.info("Rendering word search")
    st.subheader("Search Word")

    with st.form("word_search_form"):
        word = st.text_input("Word *", key="search_word")
        submitted = st.form_submit_button("Search Word")

    if submitted:
        word = word.strip()

        # Clear old search results even when the new search is invalid.
        st.session_state["word_search_results"] = None
        st.session_state["word_occurrence_index"] = 0
        st.session_state["word_search_error"] = None

        if not word:
            logger.warning("Word search rejected because input was empty")
            st.session_state["word_search_error"] = "Please enter a word."
        else:
            logger.info(f"Searching for word '%s'", word)
            try:
                st.session_state["word_search_results"] = search_word(word)
            except Exception as e:
                logger.error(f"Word search failed for '{word}' due to {e}")
                st.session_state["word_search_error"] = ("Could not search for the word. "
                                                         "Please check the application logs.")

    error = st.session_state.get("word_search_error")
    if error:
        st.error(error)
        return

    results = st.session_state.get("word_search_results")
    if results is not None:
        display_word_results(results)


def render_location_search() -> None:
    """
    Render the location-based search interface.
    Users can find a line using its global line number or its stanza position, or find a word using its position
    within a global line.
    :return: None
    """
    logger.info("Rendering location search")
    st.subheader("Search by Location")

    try:
        songs = search_songs()
    except Exception as e:
        logger.error(f"Failed to load songs for location search due to {e}")
        st.error("Could not load the song list.")
        return

    if not songs:
        st.info("Upload a song before searching by location.")
        return

    song_options = {f"{title} — {artist} (ID: {song_id})": song_id
                    for song_id, title, artist, album, year, upload_date in songs}

    selected_song = st.selectbox(
        "Select Song",
        options=list(song_options.keys()),
        key="location_song"
    )

    search_mode = st.radio(
        "Search Type",
        options=[
            "Global Line Number",
            "Stanza and Line",
            "Word Position"
        ],
        key="location_search_mode"
    )

    with st.form("location_search_form"):
        global_line_number = None
        stanza_number = None
        line_number_in_stanza = None
        position_in_line = None

        logger.debug(f"Search mode: {search_mode}")

        if search_mode in ("Global Line Number", "Word Position"):
            global_line_number = st.number_input(
                "Global Line Number",
                min_value=1,
                value=1,
                step=1
            )

        if search_mode == "Stanza and Line":
            stanza_number = st.number_input(
                "Stanza Number",
                min_value=1,
                value=1,
                step=1
            )

            line_number_in_stanza = st.number_input(
                "Line Number in Stanza",
                min_value=1,
                value=1,
                step=1
            )

        if search_mode == "Word Position":
            position_in_line = st.number_input(
                "Position in Line",
                min_value=1,
                value=1,
                step=1
            )

        submitted = st.form_submit_button("Find Location")

    if not submitted:
        return

    song_id = song_options[selected_song]

    logger.info(f"Location search submitted: song_id={song_id}, mode={search_mode}")

    try:
        if search_mode == "Global Line Number":
            result = find_line_by_global_number(song_id=song_id,
                                                global_line_number=int(global_line_number))

        elif search_mode == "Stanza and Line":
            result = find_line_by_stanza_position(song_id=song_id,
                                                  stanza_number=int(stanza_number),
                                                  line_number_in_stanza=int(line_number_in_stanza))

        else:
            result = find_word_by_position(
                song_id=song_id,
                global_line_number=int(global_line_number),
                position_in_line=int(position_in_line)
            )

        if result is None:
            logger.info(f"No result for location search: song_id={song_id}")
            st.info("No text was found at the specified location.")
            return

        st.success("Location found.")

        if search_mode == "Word Position":
            normalized_word, original_token = result
            st.write(f"**Word:** {normalized_word}")
            st.write(f"**Original Token:** {original_token}")

        else:
            st.write("**Line Text:**")
            st.text(result)

    except Exception as e:
        logger.error(f"Location search failed for song_id={song_id}, due to {e}")
        st.error("Could not search the specified location. Please check the application logs.")



def main() -> None:
    """
    Render the Search page with song, word, and location searches.
    :return: None
    """
    logger.info("Rendering search page")
    st.title("Search")

    song_tab, word_tab, location_tab = st.tabs(
        [
            "Search Songs",
            "Search Word",
            "Search by Location"
        ]
    )

    with song_tab:
        render_song_search()

    with word_tab:
        render_word_search()

    with location_tab:
        render_location_search()

    logger.info("Search page rendered successfully")


if __name__ == "__main__":
    main()
