from src.logger_config import setup_logger
from src.phrase_service import (
    get_phrases,
    get_phrase_occurrences,
    get_phrase_occurrences_with_context,
)

setup_logger()

print("PHRASES:")
for phrase in get_phrases():
    print(phrase)

print()

print("PHRASE OCCURRENCES:")
for occurrence in get_phrase_occurrences(1):
    print(occurrence)

print()

print("PHRASE OCCURRENCES WITH CONTEXT:")
for occurrence in get_phrase_occurrences_with_context(1):
    print(occurrence)