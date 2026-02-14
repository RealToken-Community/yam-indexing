from __future__ import annotations

from typing import List, Dict, Optional
from psycopg2.extensions import connection as PGConnection
from app_logging.send_telegram_alert import send_telegram_alert

from .internal._event_handlers import (
    _handle_offer_created,
    _handle_offer_accepted,
    _handle_offer_deleted,
    _handle_offer_updated,
)
from .internal._db_operations import _update_indexing_state

import logging
logger = logging.getLogger(__name__)


number_of_incorrect_the_graph_logindex = 0
def get_number_of_incorrect_the_graph_logindex() -> int:
    return number_of_incorrect_the_graph_logindex

def add_events_to_db(
    pg_conn: PGConnection,
    from_block: Optional[int],
    to_block: Optional[int],
    decoded_logs: List[Dict],
    initialisation_mode: bool = False,
    close_connection: bool = True,
) -> None:
    """
    Add YAM events to a PostgreSQL database.

    Args:
        pg_conn: Existing PostgreSQL connection
        from_block: Starting block number
        to_block: Ending block number
        decoded_logs: Decoded blockchain event logs
        initialisation_mode: If True, prints progress
        close_connection: Whether this function should close the DB connection
    """

    try:
        with pg_conn.cursor() as cursor:
            for i, log in enumerate(decoded_logs):
                event_type = log["topic"]
                
                # sometimes a wrong logindex of -1 comes out of TheGraph. We want to filter it out
                # logIndex = -1 in uint32 → 4294967295 (0xFFFFFFFF)
                if int(log["logIndex"]) >= 2**31:
                    logger.debug(f"event skipped due to wrong log index: {log}")
                    global number_of_incorrect_the_graph_logindex
                    number_of_incorrect_the_graph_logindex += 1
                    continue
                try:
                    if event_type == "OfferCreated":
                        _handle_offer_created(cursor, log)
                    elif event_type == "OfferAccepted":
                        _handle_offer_accepted(cursor, log)
                    elif event_type == "OfferUpdated":
                        _handle_offer_updated(cursor, log)
                    elif event_type == "OfferDeleted":
                        _handle_offer_deleted(cursor, log)
                except Exception as e:
                    msg = f"event not added to the DB. from block {from_block} to {to_block}. Event: {log}"
                    logger.exception(msg)
                    send_telegram_alert(msg)

                if initialisation_mode:
                    print("\r" + " " * 70, end="", flush=True)
                    print(
                        f"\r{i+1} events added to the DB out of {len(decoded_logs)} [{(i+1)/len(decoded_logs)*100:.1f}%]".ljust(60),
                        end="",
                        flush=True,
                    )

            if from_block is not None and to_block is not None:
                _update_indexing_state(cursor, from_block, to_block)

        pg_conn.commit()
    finally:
        if close_connection:
            pg_conn.close()