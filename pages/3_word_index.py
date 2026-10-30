import csv
import io
import logging
from typing import Any
import streamlit as st
from src.group_service import get_groups
from src.logger_config import setup_logger
from src.search_service import get_word_index, search_songs

setup_logger()

logger = logging.getLogger(__name__)


def get_song_options() -> dict[str, int]:
    """
    Returns all songs in a format suitable for a Streamlit selectbox.
    :return: A dictionary mapping a unique label with album and ID to its song ID.
    """
    logger.info("Fetching songs for word index filter")

    try:
        songs = search_songs()

        options = {
            f"{title} — {artist} — {album or 'No album'} (ID: {song_id})": song_id
            for (song_id, title, artist, album, publication_year, upload_date) in songs
        }

        logger.info(f'Fetched {len(options)} songs for word index filter')
        return options

    except Exception as e:
        logger.error(f"Failed to fetch songs for word index filter due to error: {e}")
        raise


def get_group_options() -> dict[str, int]:
    """
    Load named word groups for filtering the word index.
    :return: A mapping from group names to group IDs.
    """
    logger.info("Fetching word groups for word index filter")
    groups = get_groups()
    options = {group_name: group_id for group_id, group_name, *_ in groups}
    logger.info(f"Fetched {len(options)} word groups for word index filter")
    return options


def convert_index_to_rows(results: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """
    Converts raw word index query results into rows suitable for display.
    :param results: Raw rows returned from get_word_index().
    :return: A list of dictionaries containing formatted word index data.
    """
    logger.info(f'Converting {len(results)} word index records for display')
    rows: list[dict[str, Any]] = []

    for (word, song_id, song_title, stanza_number, global_line_number, line_number_in_stanza, position_in_line) in results:
        rows.append(
            {
                "Word": word,
                "Song": song_title,
                "Global Line": global_line_number,
                "Stanza": stanza_number,
                "Line in Stanza": line_number_in_stanza,
                "Position in Line": position_in_line,
            }
        )

    logger.info(f'Converted {len(rows)} word index records successfully')
    return rows


def create_csv(rows: list[dict[str, Any]]) -> str:
    """
    Creates a CSV representation of the word index.
    :param rows: Word index rows to export.
    :return: A CSV string containing the word index data.
    """
    logger.info(f'Creating CSV export for {len(rows)} word index rows')

    if not rows:
        logger.warning("CSV export requested for an empty word index")
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))

    writer.writeheader()
    writer.writerows(rows)
    csv_data = output.getvalue()
    logger.info("Word index CSV created successfully")

    return csv_data


def main() -> None:
    """
    Renders the Word Index page.
    The page displays all indexed words and their locations.
    Users can filter the index by song and/or word group and export the displayed results to CSV.
    :return: None.
    """
    logger.info("Rendering word index page")

    st.title("Word Index")
    st.write("Browse all words in the database and view their locations inside the songs.")

    try:
        song_options = get_song_options()
        group_options = get_group_options()

    except Exception as e:
        logger.error(f"Failed to load word index filter options due to error: {e}")
        st.error("Could not load the available songs or word groups.")
        return

    filter_options = {"All Songs": None, **song_options}
    selected_song_label = st.selectbox("Filter by Song", options=list(filter_options.keys()))
    selected_song_id = filter_options[selected_song_label]
    group_filter_options = {"All Groups / All Words": None, **group_options}
    selected_group_label = st.selectbox("Filter by Word Group",
                                        options=list(group_filter_options.keys()),
                                        key="index_group_filter")
    selected_group_id = group_filter_options[selected_group_label]

    logger.info(f"Word index filters selected: song={selected_song_id}, group={selected_group_id}")

    try:
        results = get_word_index(song_id=selected_song_id, group_id=selected_group_id)
        rows = convert_index_to_rows(results)

    except Exception as e:
        logger.error(f"Failed to retrieve word index data due to error: {e}")
        st.error("Could not load the word index. Please check the application logs.")
        return

    if not rows:
        logger.info("No word index records found for selected filter")
        st.info("No words were found for the selected filter.")
        return

    st.caption(f"{len(rows)} word occurrence{'s' if len(rows) != 1 else ''}")
    st.dataframe(rows, use_container_width=True, hide_index=True)
    csv_data = create_csv(rows)
    st.download_button(
        label="Export Index to CSV",
        data=csv_data,
        file_name="word_index.csv",
        mime="text/csv",
    )

    logger.info(f'Word index page rendered successfully with {len(rows)} rows')


if __name__ == "__main__":
    main()
