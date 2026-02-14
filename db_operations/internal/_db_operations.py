from __future__ import annotations

from typing import Optional
import psycopg2
from psycopg2.extensions import cursor as PGCursor, connection as PGConnection


def _update_indexing_state(
    cursor: PGCursor,
    from_block: int,
    to_block: int,
) -> None:
    cursor.execute(
        "SELECT indexing_id, from_block, to_block "
        "FROM indexing_state "
        "ORDER BY indexing_id DESC "
        "LIMIT 1"
    )
    most_recent_entry = cursor.fetchone()

    if most_recent_entry is not None:
        indexing_id, last_from, last_to = most_recent_entry
        if last_from <= from_block <= (last_to + 1) and to_block > last_to:
            cursor.execute(
                "UPDATE indexing_state SET to_block = %s WHERE indexing_id = %s",
                (to_block, indexing_id),
            )
            return

    if most_recent_entry is None or to_block > most_recent_entry[2]:
        cursor.execute(
            "INSERT INTO indexing_state (from_block, to_block) VALUES (%s, %s)",
            (from_block, to_block),
        )


def _get_last_indexed_block(conn: PGConnection) -> Optional[int]:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT to_block FROM indexing_state ORDER BY indexing_id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None
        
def _get_pg_connection(pg_host, pg_port, pg_db, pg_user, pg_password) -> PGConnection:
    """
    Create and return a PostgreSQL connection.
    """
    return psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_db,
        user=pg_user,
        password=pg_password,
        connect_timeout=10,
    )
