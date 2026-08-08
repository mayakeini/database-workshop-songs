from src.logger_config import setup_logger
from src.text_parser import parse_song

logger = setup_logger()

logger.info("Application started")

song = parse_song("sample_songs/example.txt")

for occurrence in song:
    print(occurrence)

logger.info("Application finished successfully")