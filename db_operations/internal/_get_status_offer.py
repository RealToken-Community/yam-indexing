from typing import List, Dict, Optional, Any
from psycopg2.extensions import cursor as PGCursor
from psycopg2.extras import RealDictCursor


def _get_offer_status(cursor: PGCursor, offer_id: str) -> Optional[str]:
    """
    Calculate the current status of an offer based on its event history.
    """
    events = _get_all_events_from_offer_id(cursor, offer_id)

    # Check if offer was deleted (last event is OfferDeleted)
    if len(events) > 0 and events[-1].get("event_type") == "OfferDeleted":
        return "Deleted"

    # Find the most recent 'OfferUpdated' event
    last_offer_updated_index = None
    for i, event in enumerate(events):
        if event.get("event_type") == "OfferUpdated":
            last_offer_updated_index = i

    # If an 'OfferUpdated' event was found, consider only events after that one
    if last_offer_updated_index is not None:
        events = events[last_offer_updated_index:]

    # Calculate remaining amount
    if len(events) > 0:
        initial_amount = events[0].get("initial_amount", events[0].get("amount"))

        if initial_amount is None:
            return None

        amount = int(initial_amount)

        for event in events[1:]:
            amount_bought = event.get("amount_bought")
            if amount_bought is not None:
                amount -= int(amount_bought)
    else:
        return None

    if amount == 0:
        return "SoldOut"
    elif amount > 0:
        return "InProgress"
    else:
        return None


def _get_all_events_from_offer_id_old(cursor: PGCursor, offer_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all events related to a specific offer.

    Notes for Postgres:
    - Uses %s placeholders (psycopg2 style)
    - Uses a RealDictCursor temporarily to fetch rows as dicts
      without relying on cursor.description + zip.
    """
    result: List[Dict[str, Any]] = []

    # Use a dict cursor for fetching rows as dictionaries.
    # We do it via a separate cursor so we don't depend on the calling cursor type.
    conn = cursor.connection
    with conn.cursor(cursor_factory=RealDictCursor) as dict_cur:
        dict_cur.execute("SELECT * FROM offers WHERE offer_id = %s", (offer_id,))
        offer = dict_cur.fetchone()

        if offer:
            # RealDictRow behaves like a dict; cast to plain dict for safety
            result.append(dict(offer))

            dict_cur.execute(
                "SELECT * FROM offer_events WHERE offer_id = %s ORDER BY event_timestamp ASC",
                (offer_id,),
            )
            events = dict_cur.fetchall()
            result.extend(dict(e) for e in events)

            # Sort all entries by blockchain order (block number and log index)
            result = sorted(result, key=lambda event: (event["block_number"], event["log_index"]))

    return result


def _get_all_events_from_offer_id(cursor: PGCursor, offer_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all events related to a specific offer.

    This version uses a single SELECT while preserving:
    - the exact same returned structure
    - the same keys in each dict
    - the same ordering logic
    """
    result: List[Dict[str, Any]] = []

    conn = cursor.connection
    with conn.cursor(cursor_factory=RealDictCursor) as dict_cur:
        dict_cur.execute(
            """
            SELECT
                o.offer_id,
                o.seller_address,
                o.initial_amount,
                o.price_per_unit,
                o.offer_token,
                o.buyer_token,
                o.status,
                o.block_number,
                o.transaction_hash,
                o.log_index,
                o.creation_timestamp,

                e.event_type,
                e.amount,
                e.price,
                e.buyer_address,
                e.amount_bought,
                e.price_bought,
                e.event_timestamp,
                e.unique_id,

                -- event blockchain ordering
                COALESCE(e.block_number, o.block_number) AS _block_number,
                COALESCE(e.log_index, o.log_index)       AS _log_index
            FROM offers o
            LEFT JOIN offer_events e ON e.offer_id = o.offer_id
            WHERE o.offer_id = %s
            """,
            (offer_id,),
        )

        rows = dict_cur.fetchall()

        if not rows:
            return result

        # first row = offer (same as before)
        offer = {
            "offer_id": rows[0]["offer_id"],
            "seller_address": rows[0]["seller_address"],
            "initial_amount": rows[0]["initial_amount"],
            "price_per_unit": rows[0]["price_per_unit"],
            "offer_token": rows[0]["offer_token"],
            "buyer_token": rows[0]["buyer_token"],
            "status": rows[0]["status"],
            "block_number": rows[0]["block_number"],
            "transaction_hash": rows[0]["transaction_hash"],
            "log_index": rows[0]["log_index"],
            "creation_timestamp": rows[0]["creation_timestamp"],
        }
        result.append(offer)

        # offer_events (same keys as before)
        for row in rows:
            if row["event_type"] is None:
                continue

            event = {
                "offer_id": row["offer_id"],
                "event_type": row["event_type"],
                "amount": row["amount"],
                "price": row["price"],
                "buyer_address": row["buyer_address"],
                "amount_bought": row["amount_bought"],
                "price_bought": row["price_bought"],
                "block_number": row["_block_number"],
                "log_index": row["_log_index"],
                "event_timestamp": row["event_timestamp"],
                "unique_id": row["unique_id"],
            }
            result.append(event)

        # exact same final sort
        result = sorted(result, key=lambda event: (event["block_number"], event["log_index"]))

    return result