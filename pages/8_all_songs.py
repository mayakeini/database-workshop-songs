import logging

import streamlit as st

from src.logger_config import setup_logger
from src.song_service import get_all_songs_with_counts, get_song_text

setup_logger()
logger = logging.getLogger(__name__)


def main() -> None:
    """
    Show all stored songs, counts and expandable full text.
    :return: None.
    """
    logger.info("Rendering All Songs page")
    st.title("All Songs")
    st.write("Browse every uploaded song and its stored text statistics.")

    try:
        songs = get_all_songs_with_counts()
    except Exception as e:
        logger.error(f"Failed to load the All Songs page due to {e}")
        st.error("Could not load the song collection. Please try again.")
        return

    if not songs:
        st.info("No songs have been uploaded yet.")
        return

    st.caption(f"{len(songs)} songs in the database")
    st.dataframe(
        [
            {
                "Song ID": song["song_id"],
                "Title": song["title"],
                "Artist": song["artist"],
                "Album": song["album"] or "—",
                "Year": song["publication_year"],
                "Stanzas": song["stanzas"],
                "Lines": song["lines"],
                "Words": song["words"]
            }
            for song in songs
        ],
        hide_index=True,
        width="stretch"
    )

    st.subheader("Read a Song")
    selected_song_id = st.selectbox(
        "Select Song",
        options=[song["song_id"] for song in songs],
        format_func=lambda song_id: next(f"{song['title']} — {song['artist']} (ID: {song_id})"
                                         for song in songs if song["song_id"] == song_id
        )
    )

    if selected_song_id is None:
        return

    try:
        lyrics = get_song_text(int(selected_song_id))

    except Exception as e:
        logger.error(f"Failed to reconstruct song id {selected_song_id} due to {e}")
        st.error("Could not load the selected song text.")
        return

    if lyrics:
        st.text(lyrics)
    else:
        st.info("No text was found for the selected song.")


if __name__ == "__main__":
    main()
