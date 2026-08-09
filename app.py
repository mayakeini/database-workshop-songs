from src.logger_config import setup_logger
from src.phrase_service import (
    create_and_search_phrase,
)

setup_logger()

phrase_id = create_and_search_phrase(
    phrase_name="Love Is",
    phrase_text="love is",
)

print(f"Created phrase ID: {phrase_id}")