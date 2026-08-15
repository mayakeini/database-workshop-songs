import os
import logging
import oracledb
from src.queries import db_queries

logger = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = "1521"
DEFAULT_SERVICE = "FREEPDB1"
DEFAULT_USER = "concordance"
DEFAULT_PASSWORD = "songsproject"


def get_connection():
    host = os.getenv("ORACLE_HOST", DEFAULT_HOST)
    port = os.getenv("ORACLE_PORT", DEFAULT_PORT)
    service = os.getenv("ORACLE_SERVICE", DEFAULT_SERVICE)
    user = os.getenv("ORACLE_USER", DEFAULT_USER)
    password = os.getenv("ORACLE_PASSWORD", DEFAULT_PASSWORD)

    # a web path that tells oracle where is the DB
    dsn = f"{host}:{port}/{service}"

    logger.info("Connecting to Oracle database")

    connection = oracledb.connect(
        user=user,
        password=password,
        dsn=dsn,
    )

    with connection.cursor() as cursor:
        db_queries.query_set_session_timezone(cursor)

    logger.info("Connected to Oracle successfully")

    return connection
