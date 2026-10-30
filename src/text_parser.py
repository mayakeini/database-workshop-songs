import re
from typing import List
import logging


logger = logging.getLogger(__name__)


def _normalize_word(word: str) -> str:
    """
    Converts a word into its normalized (lower-case, no special chars) form for searching.
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

            # Punctuation-only fragments are not words. Attach them to neighboring tokens so their positions remain
            # consecutive and the original punctuation survives line reconstruction.
            tokens = line.split()
            words_on_line: list[dict] = []
            leading_punctuation = ""

            for token in tokens:
                normalized = _normalize_word(token)
                if not normalized:
                    if words_on_line:
                        words_on_line[-1]["original_token"] += token
                    else:
                        leading_punctuation += token
                    continue

                position_in_song += 1
                words_on_line.append({
                    "normalized_word": normalized,
                    "original_token": leading_punctuation + token,
                    "stanza_number": stanza_number,
                    "global_line_number": global_line_number,
                    "line_number_in_stanza": line_number_in_stanza,
                    "position_in_line": len(words_on_line) + 1,
                    "position_in_song": position_in_song
                })
                leading_punctuation = ""

            # A punctuation-only line cannot be represented by the existing word-occurrence schema;
            # it contributes no word occurrences.
            if leading_punctuation and not words_on_line:
                logger.warning(f"Line {line_index + 1} in '{file_path}' contains no searchable words; "
                               f"punctuation-only content cannot be reconstructed")
            occurrences.extend(words_on_line)

    return occurrences
