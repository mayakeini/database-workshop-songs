import os
import logging

import oracledb
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_connection():
    host = os.getenv("ORACLE_HOST")
    port = os.getenv("ORACLE_PORT")
    service = os.getenv("ORACLE_SERVICE")
    user = os.getenv("ORACLE_USER")
    password = os.getenv("ORACLE_PASSWORD")

    dsn = f"{host}:{port}/{service}"

    logger.info("Connecting to Oracle database")

    connection = oracledb.connect(
        user=user,
        password=password,
        dsn=dsn,
    )

    logger.info("Connected to Oracle successfully")

    return connection