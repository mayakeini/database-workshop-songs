from datetime import datetime
import logging
import tempfile
from pathlib import Path

import streamlit as st

from src.logger_config import setup_logger
from src.song_service import insert_song

setup_logger()

logger = logging.getLogger(__name__)


def save_uploaded_file(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> str:
    """
    Saves an uploaded Streamlit file to a temporary local file.

    Args:
        uploaded_file: The TXT file uploaded by the user.

    Returns:
        The path of the temporary file.

    Raises:
        Exception: If saving the uploaded file fails.
    """
    logger.info(f"Saving uploaded file '{uploaded_file.name}' temporarily")

    try:
        suffix = Path(uploaded_file.name).suffix

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp_file:
            temp_file.write(uploaded_file.getbuffer())
            temp_path = temp_file.name

        logger.info(
            f"Uploaded file '{uploaded_file.name}' saved temporarily at '{temp_path}'",
        )

        return temp_path

    except Exception:
        logger.exception(f"Failed to save uploaded file '{uploaded_file.name}'")
        raise


def main() -> None:
    """
    Renders the song upload page and handles song insertion.

    The page allows the user to enter song metadata, upload a TXT file,
    and insert the song into the database.

    After a successful upload, the input fields are disabled and a
    success message is displayed. The user can then reset the page
    and upload another song.

    Returns:
        None.
    """
    logger.info("Rendering song upload page")

    if "file_uploader_key" not in st.session_state:
        st.session_state.file_uploader_key = 0

    if "song_uploaded_successfully" not in st.session_state:
        st.session_state.song_uploaded_successfully = False

    if "uploaded_song_id" not in st.session_state:
        st.session_state.uploaded_song_id = None

    st.title("Upload Song")

    st.write(
        "Upload a TXT file containing an English song "
        "and provide its metadata."
    )

    current_year = datetime.now().year

    title = st.text_input(
        "Song Title *",
        key="song_title",
        disabled=st.session_state.song_uploaded_successfully,
    )

    artist = st.text_input(
        "Artist *",
        key="song_artist",
        disabled=st.session_state.song_uploaded_successfully,
    )

    album = st.text_input(
        "Album",
        key="song_album",
        disabled=st.session_state.song_uploaded_successfully,
    )

    publication_year = st.number_input(
        "Publication Year *",
        min_value=1000,
        max_value=current_year,
        value=current_year,
        step=1,
        key="song_publication_year",
        disabled=st.session_state.song_uploaded_successfully,
    )

    uploaded_file = st.file_uploader(
        "Song TXT File *",
        type=["txt"],
        key=f"song_file_{st.session_state.file_uploader_key}",
        disabled=st.session_state.song_uploaded_successfully,
    )

    submitted = st.button(
        "Upload Song",
        disabled=st.session_state.song_uploaded_successfully,
        key="upload_song_button",
    )

    if st.session_state.song_uploaded_successfully:
        st.success(
            f"Song uploaded successfully. "
            f"Song ID: {st.session_state.uploaded_song_id}"
        )

        if st.button(
            "Upload Another Song",
            key="upload_another_song_button",
        ):
            logger.info("Resetting upload form")

            st.session_state.song_uploaded_successfully = False
            st.session_state.uploaded_song_id = None

            for key in [
                "song_title",
                "song_artist",
                "song_album",
                "song_publication_year",
            ]:
                if key in st.session_state:
                    del st.session_state[key]

            st.session_state.file_uploader_key += 1

            logger.info(
                "Upload page reset successfully"
            )

            st.rerun()

        return

    if not submitted:
        return

    logger.info(f"Song upload requested for title '{title}'")

    if not title.strip():
        logger.warning(
            "Song upload rejected: empty title"
        )
        st.error(
            "Song title is required."
        )
        return

    if not artist.strip():
        logger.warning(
            "Song upload rejected: empty artist"
        )
        st.error(
            "Artist is required."
        )
        return

    if uploaded_file is None:
        logger.warning(
            "Song upload rejected: no file selected"
        )
        st.error(
            "Please upload a TXT file."
        )
        return

    temp_path: str | None = None

    try:
        temp_path = save_uploaded_file(
            uploaded_file
        )

        song_id = insert_song(
            file_path=temp_path,
            title=title.strip(),
            artist=artist.strip(),
            album=(
                album.strip()
                if album.strip()
                else None
            ),
            publication_year=int(
                publication_year
            ),
        )

        logger.info(f"Song '{title}' uploaded successfully with id {song_id}")

        st.session_state.song_uploaded_successfully = True
        st.session_state.uploaded_song_id = song_id

        st.rerun()

    except ValueError as error:
        logger.warning(f"Song upload rejected for title '{title}': {error}")

        st.error(
            str(error)
        )

    except Exception:
        logger.exception(f"Failed to upload song '{title}'")

        st.error(
            "Could not upload the song. "
            "Please check the application logs for more information."
        )

    finally:
        if temp_path is not None:
            try:
                Path(temp_path).unlink(
                    missing_ok=True
                )

                logger.info(f"Temporary file '{temp_path}' deleted")

            except Exception:
                logger.exception(f"Failed to delete temporary file '{temp_path}'")


if __name__ == "__main__":
    main()