from src.logger_config import setup_logger
from src.statistics_service import (
    get_database_summary,
    get_song_statistics,
    get_most_frequent_words,
    get_rarest_words,
    get_word_length_distribution,
    get_words_per_stanza,
)

setup_logger()

print("DATABASE SUMMARY:")
print(get_database_summary())

print()

print("SONG STATISTICS:")
print(get_song_statistics(1))

print()

print("MOST FREQUENT WORDS:")
for row in get_most_frequent_words(limit=5):
    print(row)

print()

print("RAREST WORDS:")
for row in get_rarest_words(limit=5):
    print(row)

print()

print("WORD LENGTH DISTRIBUTION:")
for row in get_word_length_distribution():
    print(row)

print()

print("WORDS PER STANZA:")
for row in get_words_per_stanza(1):
    print(row)