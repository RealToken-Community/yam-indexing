from typing import Dict
from datetime import datetime
from web3 import Web3

from psycopg2.extensions import cursor as PGCursor

from ._get_status_offer import _get_offer_status


def _get_timestamp_value(log: Dict) -> datetime:
    """
    Return a Python datetime (psycopg2 adapts it to TIMESTAMPTZ).
    """
    if "timestamp" in log and log["timestamp"] is not None:
        return datetime.fromtimestamp(int(log["timestamp"]))
    return datetime.now()


def _handle_offer_created(
    cursor: PGCursor,
    log: Dict
) -> None:
    timestamp_value = _get_timestamp_value(log)

    cursor.execute(
        """
        INSERT INTO offers (
            offer_id, seller_address, initial_amount, price_per_unit,
            offer_token, buyer_token, transaction_hash, block_number, log_index,
            creation_timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (offer_id) DO NOTHING
        """,
        (
            log["offerId"],
            Web3.to_checksum_address(log["seller"]),
            str(log["amount"]),
            str(log["price"]),
            Web3.to_checksum_address(log["offerToken"]),
            Web3.to_checksum_address(log["buyerToken"]),
            log["transactionHash"],
            log["blockNumber"],
            log["logIndex"],
            timestamp_value,
        ),
    )


def _handle_offer_accepted(
    cursor: PGCursor,
    log: Dict
) -> None:
    unique_id = f"{log['transactionHash']}_{log['logIndex']}"
    timestamp_value = _get_timestamp_value(log)

    cursor.execute(
        """
        INSERT INTO offer_events (
            offer_id, event_type, buyer_address, amount_bought, price_bought,
            transaction_hash, block_number, log_index, unique_id,
            event_timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (unique_id) DO NOTHING
        """,
        (
            log["offerId"],
            log["topic"],
            Web3.to_checksum_address(log["buyer"]),
            str(log["amount"]),
            str(log["price"]),
            log["transactionHash"],
            log["blockNumber"],
            log["logIndex"],
            unique_id,
            timestamp_value,
        ),
    )

    status = _get_offer_status(cursor, log["offerId"])
    if status is not None and status != "InProgress":
        cursor.execute(
            "UPDATE offers SET status = %s WHERE offer_id = %s",
            (status, log["offerId"]),
        )


def _handle_offer_updated(
    cursor: PGCursor,
    log: Dict
) -> None:
    unique_id = f"{log['transactionHash']}_{log['logIndex']}"
    timestamp_value = _get_timestamp_value(log)

    cursor.execute(
        """
        INSERT INTO offer_events (
            offer_id, event_type, amount, price,
            transaction_hash, block_number, log_index, unique_id,
            event_timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (unique_id) DO NOTHING
        """,
        (
            log["offerId"],
            log["topic"],
            str(log["newAmount"]),
            str(log["newPrice"]),
            log["transactionHash"],
            log["blockNumber"],
            log["logIndex"],
            unique_id,
            timestamp_value,
        ),
    )

    cursor.execute(
        "UPDATE offers SET status = 'InProgress' WHERE offer_id = %s",
        (log["offerId"],),
    )


def _handle_offer_deleted(
    cursor: PGCursor,
    log: Dict
) -> None:
    unique_id = f"{log['transactionHash']}_{log['logIndex']}"
    timestamp_value = _get_timestamp_value(log)

    cursor.execute(
        """
        INSERT INTO offer_events (
            offer_id, event_type, transaction_hash, block_number, log_index,
            unique_id, event_timestamp
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (unique_id) DO NOTHING
        """,
        (
            log["offerId"],
            log["topic"],
            log["transactionHash"],
            log["blockNumber"],
            log["logIndex"],
            unique_id,
            timestamp_value,
        ),
    )

    cursor.execute(
        "UPDATE offers SET status = 'Deleted' WHERE offer_id = %s",
        (log["offerId"],),
    )
