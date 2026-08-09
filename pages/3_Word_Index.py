import csv
import io
import logging
from typing import Any

import streamlit as st

from src.logger_config import setup_logger
from src.search_service import get_word_index, search_songs

setup_logger()

logger = logging.getLogger(__name__)


def get_song_options() -> dict[str, int]:
    """
    Returns all songs in a format suitable for a Streamlit selectbox.

    Returns:
        A dictionary mapping a display label to its song ID.

    Raises:
        Exception: If retrieving the songs from the database fails.
    """
    logger.info("Fetching songs for word index filter")

    try:
        songs = search_songs()

        options = {
            f"{title} — {artist}": song_id
            for (
                song_id,
                title,
                artist,
                album,
                publication_year,
                upload_date,
            ) in songs
        }

        logger.info(
            "Fetched %s songs for word index filter",
            len(options),
        )

        return options

    except Exception:
        logger.exception(
            "Failed to fetch songs for word index filter"
        )
        raise


def convert_index_to_rows(
    results: list[tuple[Any, ...]],
) -> list[dict[str, Any]]:
    """
    Converts raw word index query results into rows suitable for display.

    Args:
        results: Raw rows returned from get_word_index().

    Returns:
        A list of dictionaries containing formatted word index data.
    """
    logger.info(
        "Converting %s word index records for display",
        len(results),
    )

    rows: list[dict[str, Any]] = []

    for (
        word,
        song_id,
        song_title,
        stanza_number,
        global_line_number,
        line_number_in_stanza,
        position_in_line,
    ) in results:

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

    logger.info(
        "Converted %s word index records successfully",
        len(rows),
    )

    return rows


def create_csv(
    rows: list[dict[str, Any]],
) -> str:
    """
    Creates a CSV representation of the word index.

    Args:
        rows: Word index rows to export.

    Returns:
        A CSV string containing the word index data.
    """
    logger.info(
        "Creating CSV export for %s word index rows",
        len(rows),
    )

    if not rows:
        logger.warning(
            "CSV export requested for an empty word index"
        )
        return ""

    output = io.StringIO()

    writer = csv.DictWriter(
        output,
        fieldnames=list(rows[0].keys()),
    )

    writer.writeheader()
    writer.writerows(rows)

    csv_data = output.getvalue()

    logger.info(
        "Word index CSV created successfully"
    )

    return csv_data


def main() -> None:
    """
    Renders the Word Index page.

    The page displays all indexed words and their locations.
    Users can optionally filter the index by song and export
    the displayed results to CSV.

    Returns:
        None.
    """
    logger.info("Rendering word index page")

    st.title("Word Index")

    st.write(
        "Browse all words in the database and view their locations "
        "inside the songs."
    )

    try:
        song_options = get_song_options()

    except Exception:
        st.error(
            "Could not load the available songs."
        )
        return

    filter_options = {
        "All Songs": None,
        **song_options,
    }

    selected_song_label = st.selectbox(
        "Filter by Song",
        options=list(filter_options.keys()),
    )

    selected_song_id = filter_options[
        selected_song_label
    ]

    logger.info(
        "Word index filter selected: %s",
        selected_song_label,
    )

    try:
        results = get_word_index(
            song_id=selected_song_id,
        )

        rows = convert_index_to_rows(results)

    except Exception:
        logger.exception(
            "Failed to retrieve word index"
        )

        st.error(
            "Could not load the word index. "
            "Please check the application logs."
        )
        return

    if not rows:
        logger.info(
            "No word index records found for selected filter"
        )

        st.info(
            "No words were found for the selected filter."
        )
        return

    st.caption(
        f"{len(rows)} word occurrence"
        f"{'s' if len(rows) != 1 else ''}"
    )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )

    csv_data = create_csv(rows)

    st.download_button(
        label="Export Index to CSV",
        data=csv_data,
        file_name="word_index.csv",
        mime="text/csv",
    )

    logger.info(
        "Word index page rendered successfully with %s rows",
        len(rows),
    )


if __name__ == "__main__":
    main()