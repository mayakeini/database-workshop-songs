import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from src.db import get_database_service
from src.queries.db_queries import *
from src.text_parser import parse_song
from src.phrase_service import refresh_existing_phrases_for_song

logger = logging.getLogger(__name__)


def song_exists(title: str, artist: str, album: str | None) -> bool:
    """
    Checks whether a song with the same title, artist, and album already exists in the database.
    The comparison is case-insensitive.
    :param title: Song title.
    :param artist: Artist name.
    :param album: Album name, or None if no album was provided.
    :return: True if a matching song already exists, otherwise False.
    """
    logger.info(f"Checking whether song already exists: title='{title}', artist='{artist}', album='{album}'")

    try:
        with get_database_service().read_cursor() as cursor:
            query_count_matching_song(
                cursor,
                title=title,
                artist=artist,
                album=album
            )
            count = cursor.fetchone()[0]
            exists = count > 0
            logger.info(f'Song existence check completed. Exists={exists}')
            return exists

    except Exception as e:
        logger.error(f"Failed to check whether song '{title}' already exists due to {e}")
        raise
        

def insert_song(file_path: str, title: str, artist: str, album: str | None, publication_year: int) -> int:
    """
    Parses a song file and inserts the song, stanzas, words, and word occurrences into the database.
    :param file_path: Path to the TXT song file.
    :param title: Song title.
    :param artist: Artist name.
    :param album: Optional album name.
    :param publication_year: Year the song was published.
    :return: The database ID of the inserted song.
    """
    title = title.strip()
    artist = artist.strip()
    album = album.strip() if album and album.strip() else None

    logger.info(f"Starting song insertion: '{title}' by '{artist}'")

    current_year = datetime.now(ZoneInfo("Asia/Jerusalem")).year

    if publication_year < 1000 or publication_year > current_year:
        logger.warning(f'Song insertion rejected due to invalid publication year: {publication_year}')
        raise ValueError(f"Publication year must be between 1000 and {current_year}.")

    if song_exists(title, artist, album):
        logger.warning(f"Song insertion rejected because it already exists: '{title}' by '{artist}'")
        if album:
          raise ValueError(f"The song '{title}' ({album}) by '{artist}' already exists.")
        else:
          raise ValueError(f"The song '{title}' by '{artist}' already exists.")

    occurrences = parse_song(file_path)

    if not occurrences:
        logger.warning(f'Song upload rejected because the file contains no valid words: {file_path}')
        raise ValueError("The uploaded song file is empty or contains no valid words.")

    try:
        with get_database_service().transaction() as cursor:
            song_id_var = cursor.var(int)
            israel_time = datetime.now(ZoneInfo("Asia/Jerusalem"))
            logger.info(f'Using Israel upload time: {israel_time}')

            query_insert_song_returning_id(
                cursor,
                title=title,
                artist=artist,
                album=album,
                publication_year=publication_year,
                upload_date=israel_time,
                song_id=song_id_var
            )

            song_id = song_id_var.getvalue()[0]
            logger.info(f'Inserted song with id {song_id}')

            stanza_ids: dict[int, int] = {}
            for occurrence in occurrences:
                stanza_number = occurrence["stanza_number"]

                if stanza_number in stanza_ids:
                    continue

                stanza_id_var = cursor.var(int)
                query_insert_stanza_returning_id(
                    cursor,
                    song_id=song_id,
                    stanza_number=stanza_number,
                    stanza_id=stanza_id_var
                )

                stanza_id = stanza_id_var.getvalue()[0]
                stanza_ids[stanza_number] = stanza_id

                logger.debug(f'Inserted stanza {stanza_number} with id {stanza_id} for song id {song_id}')

            word_ids: dict[str, int] = {}

            for occurrence in occurrences:
                word = occurrence["normalized_word"]

                if word not in word_ids:
                    query_select_word_id_by_text(cursor, word)
                    row = cursor.fetchone()

                    if row is not None:
                        word_id = row[0]
                        logger.debug(f"Using existing word '{word}' with id {word_id}")

                    else:
                        word_id_var = cursor.var(int)
                        query_insert_word_returning_id(cursor, word=word, word_id=word_id_var)
                        word_id = word_id_var.getvalue()[0]
                        logger.debug(f"Inserted new word '{word}' with id {word_id}")

                    word_ids[word] = word_id

                query_insert_word_occurrence(
                    cursor,
                    word_id=word_ids[word],
                    song_id=song_id,
                    stanza_id=stanza_ids[occurrence["stanza_number"]],
                    global_line_number=occurrence["global_line_number"],
                    line_number_in_stanza=occurrence["line_number_in_stanza"],
                    position_in_line=occurrence["position_in_line"],
                    position_in_song=occurrence["position_in_song"],
                    original_token=occurrence["original_token"]
                )

            updated_phrase_occurrences = refresh_existing_phrases_for_song(cursor=cursor, song_id=song_id)
            logger.info(f"Added {updated_phrase_occurrences} existing phrase occurrences for song id {song_id}")

        logger.info(f"Song inserted successfully: '{title}' ({len(occurrences)} occurrences)")
        return song_id

    except Exception as e:
        logger.error(f"Failed to insert song: '{title}' due to '{e}'")
        raise


def get_line(song_id: int, global_line_number: int) -> str:
    """
    get a specific line of a song.
    :param song_id: The database ID of the song.
    :param global_line_number: The global line number in the song.
    :return: The complete song line. Returns an empty string if the requested line does not exist.
    """
    logger.info(f'Fetching line {global_line_number} for song id {song_id}')

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_line_tokens_by_global_number(cursor, song_id, global_line_number)
            tokens = [row[0] for row in cursor.fetchall()]
            line = " ".join(tokens)
            logger.info(f'Line {global_line_number} for song id {song_id} reconstructed successfully')
            return line

    except Exception as e:
        logger.error(f'Failed to fetch line {global_line_number} for song id {song_id} due to {e}')
        raise


def get_song_text(song_id: int) -> str:
    """
    get the complete text of a song from its word occurrences.
    Blank lines are inserted between stanzas.
    :param song_id: The database ID of the song.
    :return: The complete song text. Returns an empty string if the song has no word occurrences.
    """
    logger.info(f'Fetching complete text for song id {song_id}')

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_song_text_rows(cursor, song_id)
            rows = cursor.fetchall()

            if not rows:
                logger.info(f'No text found for song id {song_id}')
                return ""

            result: list[str] = []
            current_stanza: int | None = None
            current_line: int | None = None
            line_tokens: list[str] = []

            for stanza_number, line_number, position, token in rows:
                if current_stanza is not None and stanza_number != current_stanza:
                    if line_tokens:
                        result.append(" ".join(line_tokens))
                        line_tokens = []

                    result.append("")

                elif current_line is not None and line_number != current_line:
                    result.append(" ".join(line_tokens))
                    line_tokens = []

                line_tokens.append(token)
                current_stanza = stanza_number
                current_line = line_number

            if line_tokens:
                result.append(" ".join(line_tokens))

            song_text = "\n".join(result)
            logger.info(f'Complete text for song id {song_id} reconstructed successfully')
            return song_text

    except Exception as e:
        logger.error(f'Failed to reconstruct text for song id {song_id} due to {e}')
        raise


def get_uploaded_song_summary(song_id: int) -> dict[str, int]:
    """
    Return saved stanza, line and word occurrence counts for one song.
    :param song_id: ID of the successfully uploaded song.
    :return: Mapping with the keys stanzas, lines and words.
    """
    logger.info(f"Getting upload summary for song id {song_id}")

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_uploaded_song_summary(cursor, song_id)
            row = cursor.fetchone()
        result = {
            "stanzas": int(row[0]) if row else 0,
            "lines": int(row[1]) if row else 0,
            "words": int(row[2]) if row else 0
        }
        logger.info(f"Upload summary for song id {song_id}: {result}")
        return result

    except Exception as e:
        logger.error(f"Failed to load upload summary for song id {song_id} due to {e}")
        raise


def get_all_songs_with_counts() -> list[dict[str, str | int | None]]:
    """
    Fetch every song with counts of saved stanzas, lines and word tokens.
    :return: Rows containing metadata and counts for each song, including songs with no occurrences (reported as zero).
    """
    logger.info("Loading all songs with saved text counts")

    try:
        with get_database_service().read_cursor() as cursor:
            query_select_all_songs_with_counts(cursor)
            rows = cursor.fetchall()

        results = [
            {
                "song_id": int(song_id),
                "title": title,
                "artist": artist,
                "album": album,
                "publication_year": int(year),
                "stanzas": int(stanzas),
                "lines": int(lines),
                "words": int(words)
            }
            for song_id, title, artist, album, year, stanzas, lines, words in rows
        ]

        logger.info(f"Loaded {len(results)} songs with counts")
        return results

    except Exception as e:
        logger.error(f"Failed to load all songs with counts due to {e}")
        raise


def delete_song(song_id: int) -> bool:
    """
    Delete a single song and its stanzas and occurrences in one transaction.
    Shared words, groups and phrase definitions are preserved.
    :param song_id: ID of the song to delete.
    :return: True if the song was deleted, False if some failure to delete
    """
    logger.info("Deleting song id %s", song_id)

    try:
        with get_database_service().transaction() as cursor:
            query_delete_song(cursor, song_id)
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info("Song id %s deleted successfully", song_id)
        else:
            logger.warning("Song id %s was not found", song_id)
        return deleted

    except Exception:
        logger.exception("Failed to delete song id %s", song_id)
        raise
