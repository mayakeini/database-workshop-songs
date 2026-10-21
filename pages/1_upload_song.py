from datetime import datetime
import logging
import tempfile
from pathlib import Path

import streamlit as st

from src.logger_config import setup_logger
from src.song_service import insert_song, get_uploaded_song_summary

setup_logger()

logger = logging.getLogger(__name__)


def save_uploaded_file(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> str:
    """
    Saves an uploaded Streamlit file to a temporary local file.
    :param uploaded_file: The TXT file uploaded by the user.
    :return: str of the path of the temporary file.
    """
    logger.info(f"Saving uploaded file '{uploaded_file.name}' temporarily")
    try:
        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix,) as temp_file:
            temp_file.write(uploaded_file.getbuffer())
            temp_path = temp_file.name

        logger.info(f"Uploaded file '{uploaded_file.name}' saved temporarily at '{temp_path}'")
        return temp_path

    except Exception as e:
        logger.error(f"Failed to save uploaded file '{uploaded_file.name}' due to '{e}'")
        raise



def validate_uploaded_txt_file(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> None:
    """
    Validate that an upload is a readable UTF-8 TXT file.
    :param uploaded_file: File supplied by the Streamlit uploader.
    :return: None
    """
    logger.info("Validating uploaded TXT file")
    filename = uploaded_file.name
    if Path(filename).suffix.lower() != ".txt":
        logger.warning("Rejected upload with non-TXT extension: %s", filename)
        raise ValueError("Only .txt files are supported. Please select a TXT file.")

    content = uploaded_file.getvalue()
    if not content:
        logger.warning("Rejected empty TXT upload: %s", filename)
        raise ValueError("The TXT file is empty. Please select a non-empty file.")

    if b"\x00" in content:
        logger.warning("Rejected binary upload disguised as TXT: %s", filename)
        raise ValueError("This file is not a valid text file. Please upload a UTF-8 TXT file.")

    try:
        content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        logger.warning("Rejected non-UTF-8 upload: %s", filename)
        raise ValueError(
            "The file could not be read as UTF-8 text. "
            "Please save it as a UTF-8 TXT file and try again."
        ) from error

    logger.info("Validated TXT upload: %s", filename)


def main() -> None:
    """
    Renders the song upload page and handles song insertion. The page allows the user to enter song metadata, upload
    a TXT file, and insert the song into the database. After a successful upload, the input fields are disabled and a
    success message is displayed. The user can then reset the page
    and upload another song.
    :return: None
    """
    logger.info("Rendering song upload page")
    if "file_uploader_key" not in st.session_state:
        st.session_state.file_uploader_key = 0

    if "song_uploaded_successfully" not in st.session_state:
        st.session_state.song_uploaded_successfully = False

    if "uploaded_song_id" not in st.session_state:
        st.session_state.uploaded_song_id = None

    if "uploaded_song_summary" not in st.session_state:
        st.session_state.uploaded_song_summary = None

    st.title("Upload Song")
    st.write("Upload a TXT file containing an English song and provide its metadata.")

    current_year = datetime.now().year

    title = st.text_input(
        "Song Title *",
        key="song_title",
        disabled=st.session_state.song_uploaded_successfully
    )

    artist = st.text_input(
        "Artist *",
        key="song_artist",
        disabled=st.session_state.song_uploaded_successfully
    )

    album = st.text_input(
        "Album",
        key="song_album",
        disabled=st.session_state.song_uploaded_successfully
    )

    publication_year = st.number_input(
        "Publication Year *",
        min_value=1000,
        max_value=current_year,
        value=current_year,
        step=1,
        key="song_publication_year",
        disabled=st.session_state.song_uploaded_successfully
    )

    uploaded_file = st.file_uploader(
        "Song TXT File *",
        type=["txt"],
        key=f"song_file_{st.session_state.file_uploader_key}",
        disabled=st.session_state.song_uploaded_successfully
    )

    submitted = st.button(
        "Upload Song",
        disabled=st.session_state.song_uploaded_successfully,
        key="upload_song_button"
    )

    if st.session_state.song_uploaded_successfully:
        st.success(f"Song ID {st.session_state.uploaded_song_id} uploaded successfully.")

        summary = st.session_state.uploaded_song_summary
        if summary is not None:
            st.write("**Upload Summary**")
            col_stanzas, col_lines, col_words = st.columns(3)
            col_stanzas.metric("Stanzas", summary["stanzas"])
            col_lines.metric("Lines", summary["lines"])
            col_words.metric("Words", summary["words"])
        else:
            logger.warning("Song upload rejected: summary is empty")

        if st.button(
            "Upload Another Song",
            key="upload_another_song_button",
        ):
            logger.info("Resetting upload form")

            st.session_state.song_uploaded_successfully = False
            st.session_state.uploaded_song_id = None
            st.session_state.uploaded_song_summary = None

            for key in [
                "song_title",
                "song_artist",
                "song_album",
                "song_publication_year",
            ]:
                if key in st.session_state:
                    del st.session_state[key]

            st.session_state.file_uploader_key += 1

            logger.info("Upload page reset successfully")

            st.rerun()

        return

    if not submitted:
        return

    logger.info(f"Song upload requested for title '{title}'")

    if not title.strip():
        logger.warning("Song upload rejected: empty title")
        st.error("Song title is required.")
        return

    if not artist.strip():
        logger.warning("Song upload rejected: empty artist")
        st.error("Artist is required.")
        return

    if uploaded_file is None:
        logger.warning("Song upload rejected: no file selected")
        st.error("Please upload a TXT file.")
        return

    temp_path: str | None = None

    try:
        validate_uploaded_txt_file(uploaded_file)
        temp_path = save_uploaded_file(uploaded_file)

        song_id = insert_song(
            file_path=temp_path,
            title=title.strip(),
            artist=artist.strip(),
            album=(album.strip() if album.strip() else None),
            publication_year=int(publication_year)
        )

        logger.info(f"Song '{title}' uploaded successfully with id {song_id}")

        # The upload has committed. Fetch the persisted counts for display.
        st.session_state.song_uploaded_successfully = True
        st.session_state.uploaded_song_id = song_id

        try:
            st.session_state.uploaded_song_summary = get_uploaded_song_summary(song_id)
        except Exception as e:
            logger.error(f"Song id {song_id} uploaded, but summary could not be loaded due to error: {e}")
            st.session_state.uploaded_song_summary = None

        st.rerun()

    except ValueError as error:
        logger.warning(f"Song upload rejected for title '{title}': {error}")
        st.error(str(error))

    except Exception as e:
        logger.error(f"Failed to upload song '{title}' due to error: {e}")

        st.error("Could not upload the song. Please check the application logs for more information.")

    finally:
        if temp_path is not None:
            try:
                Path(temp_path).unlink(missing_ok=True)
                logger.info(f"Temporary file '{temp_path}' deleted")

            except Exception as e:
                logger.error(f"Failed to delete temporary file '{temp_path}' due to error: {e}")


if __name__ == "__main__":
    main()