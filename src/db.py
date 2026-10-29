import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
import oracledb
import streamlit as st
from src.queries import db_queries

logger = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = "1521"
DEFAULT_SERVICE = "FREEPDB1"
DEFAULT_USER = "concordance"
DEFAULT_PASSWORD = "songsproject"


class DatabaseService:
    """
    Manage pooled connections and one transaction per write operation.
    Only the pool is shared. Connections and cursors belong to the individual context that acquired them
    and must not be used after that context exits.
    """

    def __init__(self, pool: oracledb.ConnectionPool) -> None:
        self.oracle_con_pool = pool

    @contextmanager
    def read_cursor(self) -> Iterator[oracledb.Cursor]:
        """
        Yield a cursor without committing, then release both resources.
        Oracle rolls back any uncommitted work when the connection is returned to the pool. Fetch results inside
        this context before returning them.
        :return: a cursor without committing, then release both resources.
        """
        with self.oracle_con_pool.acquire() as connection:
            with connection.cursor() as cursor:
                yield cursor

    @contextmanager
    def transaction(self) -> Iterator[oracledb.Cursor]:
        """
        Commit the entire block on success or roll back and propagate errors.
        Pass this cursor to every query in the operation. Opening another transaction context acquires a separate
        connection and transaction.
        :return: a cursor without committing, then release both resources.
        """
        with self.oracle_con_pool.acquire() as connection:
            try:
                with connection.cursor() as cursor:
                    yield cursor
                connection.commit()
            except BaseException:
                try:
                    connection.rollback()
                except Exception as e:
                    # A lost connection can also make rollback fail. Preserve
                    # the operation's original error for its caller.
                    logger.error(f"Failed to roll back database transaction due to {e}")
                raise

    def close(self) -> None:
        """
        Close the pool after all callers have released their connections.
        :return: None
        """
        self.oracle_con_pool.close()


def _initialize_session(connection: oracledb.Connection, _) -> None:
    """
    Initialize each new pooled session before it is handed to a caller.
    Oracle passes 2 arguments but the fucntion only needs one. so use _ as placeholder for the second parameter
    :param connection: The Oracle connection being initialized.
    :return: None
    """
    with connection.cursor() as cursor:
        db_queries.query_set_session_timezone(cursor)


@st.cache_resource(show_spinner=False)
def get_database_service() -> DatabaseService:
    """
    Lazily create one service shared across Streamlit sessions and reruns.
    Configuration is read when the pool is created. Restart the app after changing its Oracle environment variables.
    :return: a database service shared across Streamlit sessions and reruns
    """
    host = os.getenv("ORACLE_HOST", DEFAULT_HOST)
    port = os.getenv("ORACLE_PORT", DEFAULT_PORT)
    service = os.getenv("ORACLE_SERVICE", DEFAULT_SERVICE)
    user = os.getenv("ORACLE_USER", DEFAULT_USER)
    password = os.getenv("ORACLE_PASSWORD", DEFAULT_PASSWORD)

    dsn = f"{host}:{port}/{service}"

    logger.info("Creating Oracle connection pool")

    pool = oracledb.create_pool(
        user=user,
        password=password,
        dsn=dsn,
        min=1,
        max=4,
        increment=1,
        getmode=oracledb.POOL_GETMODE_TIMEDWAIT,
        wait_timeout=5000,
        session_callback=_initialize_session,
    )

    logger.info("Oracle connection pool created")

    return DatabaseService(pool)
