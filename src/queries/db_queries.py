def query_set_session_timezone(cursor):
    cursor.execute(
        "ALTER SESSION SET TIME_ZONE = '+03:00'"
    )
