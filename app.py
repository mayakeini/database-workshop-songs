from src.logger_config import setup_logger
from src.search_service import (
    get_word_index,
    find_line_by_global_number,
    find_line_by_stanza_position,
    find_word_by_position,
)

setup_logger()

print("WORD INDEX:")
for row in get_word_index(1):
    print(row)

print()

print("GLOBAL LINE 3:")
print(find_line_by_global_number(1, 3))

print()

print("STANZA 2, LINE 1:")
print(find_line_by_stanza_position(1, 2, 1))

print()

print("WORD AT LINE 3, POSITION 4:")
print(find_word_by_position(1, 3, 4))