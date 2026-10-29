import logging

import streamlit as st

from src.logger_config import setup_logger
from src.song_service import delete_song, get_all_songs_with_counts

setup_logger()
logger = logging.getLogger(__name__)


def select_song_for_deletion(song_id: int | None) -> None:
    """Select one inline confirmation, or close it without deleting anything."""
    st.session_state["delete_song_pending_id"] = song_id


def clear_deleted_song_results(song_id: int) -> None:
    """Discard this session's search results and any upload receipt for the song."""
    st.session_state["word_search_results"] = None
    st.session_state["word_occurrence_index"] = 0
    st.session_state["word_search_error"] = None

    if st.session_state.get("uploaded_song_id") == song_id:
        st.session_state["song_uploaded_successfully"] = False
        st.session_state["uploaded_song_id"] = None
        st.session_state["uploaded_song_summary"] = None
        for key in ("song_title", "song_artist", "song_album", "song_publication_year"):
            st.session_state.pop(key, None)
        st.session_state["file_uploader_key"] = st.session_state.get("file_uploader_key", 0) + 1


def render_confirmation(song_id: int, title: str, artist: str) -> None:
    """Delete only after Yes; retain the confirmation when a deletion fails."""
    st.text(f'Are you sure you want to delete "{title}" by {artist}?')
    yes_column, no_column = st.columns(2)
    confirmed = yes_column.button("Yes", key=f"confirm_delete_song_{song_id}", type="primary")
    no_column.button(
        "No",
        key=f"cancel_delete_song_{song_id}",
        on_click=select_song_for_deletion,
        args=(None,),
    )

    if not confirmed:
        return

    try:
        deleted = delete_song(song_id)
    except Exception:
        logger.exception("Could not delete song id %s from the Delete Song page", song_id)
        st.error("Could not delete the song. Please try again.")
        return

    clear_deleted_song_results(song_id)
    st.session_state.pop("delete_song_pending_id", None)
    if deleted:
        st.session_state["delete_song_notice"] = ("success", f'Song "{title}" by {artist} deleted.')
    else:
        st.session_state["delete_song_notice"] = ("warning", "This song no longer exists.")
    st.rerun()


def main() -> None:
    """List every song with its own Delete button and inline Yes/No confirmation."""
    st.title("Delete Song")
    st.write("Choose a song to delete, then confirm below its details.")

    notice = st.session_state.pop("delete_song_notice", None)
    if notice is not None:
        level, message = notice
        if level == "success":
            st.success(message)
        else:
            st.warning(message)

    try:
        songs = get_all_songs_with_counts()
    except Exception:
        logger.exception("Failed to load the Delete Song page")
        st.error("Could not load the song collection. Please try again.")
        return

    pending_id = st.session_state.get("delete_song_pending_id")
    if pending_id is not None and not any(song["song_id"] == pending_id for song in songs):
        st.session_state.pop("delete_song_pending_id", None)
        clear_deleted_song_results(pending_id)
        st.warning("This song no longer exists.")

    if not songs:
        st.info("No songs have been uploaded yet.")
        return

    st.caption(f"{len(songs)} {'song' if len(songs) == 1 else 'songs'} in the database")
    for song in songs:
        song_id = int(song["song_id"])
        with st.container(border=True):
            details, action = st.columns([5, 1], vertical_alignment="center")
            with details:
                st.text(f"{song['title']} — {song['artist']}")
                st.caption(f"Album: {song['album'] or '—'} · {song['publication_year']} · ID: {song_id}")
            action.button(
                "Delete",
                key=f"delete_song_{song_id}",
                on_click=select_song_for_deletion,
                args=(song_id,),
            )
            if st.session_state.get("delete_song_pending_id") == song_id:
                render_confirmation(song_id, song["title"], song["artist"])


if __name__ == "__main__":
    main()
