from psycopg2.extensions import connection as PGConnection
from psycopg2.extras import Json


def store_event_in_queue(pg_conn: PGConnection, log: dict) -> None:
    """
    Store a single event log into the event_queue table.

    :param conn: psycopg2 connection
    :param log: decoded log dict to store as JSONB
    """
    query = """
        INSERT INTO public.event_queue (payload)
        VALUES (%s)
    """

    with pg_conn.cursor() as cursor:
        cursor.execute(query, (Json(log),))

    pg_conn.commit()
