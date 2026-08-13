import logging

from src.db import get_connection

logger = logging.getLogger(__name__)


def search_songs(title=None, artist=None, album=None, publication_year=None):
    """
    Search songs based on title and artist & album title
    :param title: title of the song
    :param artist: song's artist
    :param album: song's album
    :param publication_year: song's publication year
    :return:
    """
    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                song_id,
                title,
                artist,
                album,
                publication_year,
                TO_CHAR(
                    upload_date,
                    'YYYY-MM-DD HH24:MI:SS TZH:TZM'
                ) AS upload_date
            FROM songs
            WHERE 1 = 1
        """

        params = {}

        if title:
            query += " AND LOWER(title) LIKE LOWER(:title)"
            params["title"] = f"%{title}%"

        if artist:
            query += " AND LOWER(artist) LIKE LOWER(:artist)"
            params["artist"] = f"%{artist}%"

        if album:
            query += " AND LOWER(album) LIKE LOWER(:album)"
            params["album"] = f"%{album}%"

        if publication_year:
            query += " AND publication_year = :publication_year"
            params["publication_year"] = publication_year

        query += " ORDER BY title"

        cursor.execute(query, params)

        return cursor.fetchall()

    finally:
        connection.close()


def search_word(word: str):
    """
    Search words
    :param word: str of the word
    :return:
    """
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                wo.occurrence_id,
                s.song_id,
                s.title,
                s.artist,
                st.stanza_number,
                wo.global_line_number,
                wo.line_number_in_stanza,
                wo.position_in_line,
                wo.position_in_song,
                wo.original_token
            FROM words w
            JOIN word_occurrences wo
                ON w.word_id = wo.word_id
            JOIN songs s
                ON wo.song_id = s.song_id
            JOIN stanzas st
                ON wo.stanza_id = st.stanza_id
            WHERE w.text = LOWER(:word)
            ORDER BY
                s.song_id,
                wo.position_in_song
            """,
            word=word,
        )

        return cursor.fetchall()

    finally:
        connection.close()


def get_context(song_id: int, global_line_number: int) -> dict:
    """
    Get context for the song
    :param song_id: int of the song
    :param global_line_number: int of the global line number
    :return: dictionary of the context for the song
    """
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                global_line_number,
                position_in_line,
                original_token
            FROM word_occurrences
            WHERE song_id = :song_id
              AND global_line_number BETWEEN :previous_line AND :next_line
            ORDER BY
                global_line_number,
                position_in_line
            """,
            song_id=song_id,
            previous_line=global_line_number - 1,
            next_line=global_line_number + 1,
        )

        rows = cursor.fetchall()

        lines = {}

        for line_number, position, token in rows:
            if line_number not in lines:
                lines[line_number] = []

            lines[line_number].append(token)

        return {
            line_number: " ".join(tokens)
            for line_number, tokens in lines.items()
        }

    finally:
        connection.close()


def get_word_index(song_id=None) -> dict:
    """
    Get word index by song id
    :param song_id: the song id, None by default
    :return: int of the word index
    """
    logger.info(fr"Get the word index of song id {song_id}")
    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                w.text,
                s.song_id,
                s.title,
                st.stanza_number,
                wo.global_line_number,
                wo.line_number_in_stanza,
                wo.position_in_line
            FROM words w
            JOIN word_occurrences wo
                ON w.word_id = wo.word_id
            JOIN songs s
                ON wo.song_id = s.song_id
            JOIN stanzas st
                ON wo.stanza_id = st.stanza_id
        """

        params = {}

        if song_id is not None:
            query += " WHERE s.song_id = :song_id"
            params["song_id"] = song_id

        query += """
            ORDER BY
                w.text,
                s.song_id,
                wo.position_in_song
        """

        cursor.execute(query, params)

        return cursor.fetchall()

    finally:
        connection.close()


def find_line_by_global_number(song_id: int, global_line_number:int) -> dict:
    """
    Find line by song id and global line number
    :param song_id: int of the song id
    :param global_line_number: int of the global line number
    :return: dictionary of the context for the song
    """
    logger.info(fr"Find the line in line number: {global_line_number} of the song id: {song_id}")
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT original_token
            FROM word_occurrences
            WHERE song_id = :song_id
              AND global_line_number = :global_line_number
            ORDER BY position_in_line
            """,
            song_id=song_id,
            global_line_number=global_line_number,
        )

        tokens = [row[0] for row in cursor.fetchall()]

        if not tokens:
            return None

        return " ".join(tokens)

    finally:
        connection.close()


def find_line_by_stanza_position(song_id: int, stanza_number: int, line_number_in_stanza: int) -> dict:
    """
    Get line by song id and stanza position
    :param song_id: int of the song id
    :param stanza_number: int of the stanza number
    :param line_number_in_stanza: int of the stanza number
    :return: dictionary of the context for the song
    """
    logger.info(fr"Find the line of the song id {song_id} and stanza number {stanza_number}. Line number in stanza is {line_number_in_stanza}")
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT wo.original_token
            FROM word_occurrences wo
            JOIN stanzas st
                ON wo.stanza_id = st.stanza_id
            WHERE wo.song_id = :song_id
              AND st.stanza_number = :stanza_number
              AND wo.line_number_in_stanza = :line_number_in_stanza
            ORDER BY wo.position_in_line
            """,
            song_id=song_id,
            stanza_number=stanza_number,
            line_number_in_stanza=line_number_in_stanza,
        )

        tokens = [row[0] for row in cursor.fetchall()]

        if not tokens:
            return None

        return " ".join(tokens)

    finally:
        connection.close()


def find_word_by_position(song_id: int, global_line_number: int, position_in_line: int) -> dict:
    """
    Find word by song id, global line number and position in line
    :param song_id: int of the song id
    :param global_line_number: int of the global line number
    :param position_in_line: int of the position in line
    :return: dictionary of the context for the song
    """
    logger.info(fr"Find the word in line number: {position_in_line} of the song id: {song_id}. The word position is {global_line_number}")
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                w.text,
                wo.original_token
            FROM word_occurrences wo
            JOIN words w
                ON wo.word_id = w.word_id
            WHERE wo.song_id = :song_id
              AND wo.global_line_number = :global_line_number
              AND wo.position_in_line = :position_in_line
            """,
            song_id=song_id,
            global_line_number=global_line_number,
            position_in_line=position_in_line,
        )

        return cursor.fetchone()

    finally:
        connection.close()
