import logging
from typing import List, Dict, Any
from psycopg2.extensions import connection as PGConnection
from db_operations import add_events_to_db
from the_graphe_handler.internals import (
    fetch_offer_accepted_from_block_range,
    fetch_offer_created_from_block_range, 
    fetch_offer_updated_from_block_range,
    fetch_offer_deleted_from_block_range
)


def backfill_db_block_range(
    pg_conn: PGConnection,
    subgraph_url: str, 
    the_graph_api_key: str,
    last_block_indexed: int,
    latest_block_number: int
) -> None:
    """
    Backfill the database with YAM events from a specified block range.
    
    This function fetches all YAM marketplace events (created, accepted, updated, deleted)
    from TheGraph subgraph within the given block range and adds them to the local database
    in chronological order based on their timestamps.
    
    Args:
        db_path (str): Path to the local database file
        subgraph_url (str): URL of TheGraph subgraph endpoint
        the_graph_api_key (str): API key for TheGraph authentication
        last_block_indexed (int): The last block number that was previously indexed (inclusive)
        latest_block_number (Optional[int]): The ending block number (inclusive). If None, fetches to latest block
        
    Returns:
        None
        
    Raises:
        Exception: If any of the fetch operations or database operations fail
        
    """
    
    # Initialize logger for this module
    logger = logging.getLogger(__name__)
    
    try:
        # Fetch all offer events from TheGraph subgraph within the specified block range
        # Each fetch function returns a list of events for that specific event type
        
        print(f"Backfilling DB events from block {last_block_indexed} to block {latest_block_number} from TheGraph...")
        
        created_offers: List[Dict[str, Any]] = fetch_offer_created_from_block_range(subgraph_url, the_graph_api_key, last_block_indexed, latest_block_number)
        accepted_offers: List[Dict[str, Any]] = fetch_offer_accepted_from_block_range(subgraph_url, the_graph_api_key, last_block_indexed, latest_block_number)
        updated_offers: List[Dict[str, Any]] = fetch_offer_updated_from_block_range(subgraph_url, the_graph_api_key, last_block_indexed, latest_block_number)
        deleted_offers: List[Dict[str, Any]] = fetch_offer_deleted_from_block_range(subgraph_url, the_graph_api_key, last_block_indexed, latest_block_number)
        
        # Combine all event types into a single list
        all_events = (created_offers + accepted_offers + updated_offers + deleted_offers)
        
        # Sort events chronologically by timestamp to maintain proper event ordering
        # This ensures that events are processed in the correct temporal sequence
        all_events_sorted = sorted(all_events, key=lambda event: event['timestamp'])
        
        # Add all sorted events to the database
        add_events_to_db(pg_conn, last_block_indexed, latest_block_number, all_events_sorted)
        
        logger.info(f"Backfilling successful - {len(all_events_sorted)} YAM events fetched from the graph between block {last_block_indexed} and block {latest_block_number}.")
        
    except Exception as e:
        logger.error(
            f"Failed to backfill database for block range {last_block_indexed}-{latest_block_number}: {e}"
        )
        raise