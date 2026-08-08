import re
from typing import List

import logging

logger = logging.getLogger(__name__)


def _normalize_word(word: str) -> str:
    """
    Converts a word into its normalized form for searching.
    Example:
    'Hello,' -> 'hello'
    'world!' -> 'world'

    :param word: word to normalize
    :return: normalized word as string
    """
    logger.debug(fr"Normalizing {word} word")
    return re.sub(r"[^a-zA-Z']", "", word).lower()


def parse_song(file_path: str) -> List[dict]:
    """
    Reads a song text file and returns structured word occurrences.

    Each occurrence contains:
    - normalized word
    - original token
    - stanza number
    - global line number
    - line number inside stanza
    - position inside line
    - position inside song

    :param file_path: path to song text file
    :return: list of occurrences
    """
    logger.info(f"Start parsing {file_path} file path")

    occurrences = []

    stanza_number = 1
    global_line_number = 0
    line_number_in_stanza = 0
    position_in_song = 0

    with open(file_path, "r", encoding="utf-8") as file:
        for line_index, raw_line in enumerate(file):
            logger.debug(fr"Parsing {file_path} line {line_index + 1}")
            line = raw_line.strip()

            # Empty line = new stanza
            if not line:
                if line_number_in_stanza > 0:
                    stanza_number += 1
                    line_number_in_stanza = 0
                continue

            global_line_number += 1
            line_number_in_stanza += 1

            tokens = line.split()

            for position_in_line, token in enumerate(tokens, start=1):
                normalized = _normalize_word(token)

                if not normalized:
                    continue

                position_in_song += 1

                occurrences.append({
                    "normalized_word": normalized,
                    "original_token": token,
                    "stanza_number": stanza_number,
                    "global_line_number": global_line_number,
                    "line_number_in_stanza": line_number_in_stanza,
                    "position_in_line": position_in_line,
                    "position_in_song": position_in_song,
                })

    return occurrences