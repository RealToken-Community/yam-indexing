import requests
import time
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def fetch_all_offer_accepted(api_key: str, url: str, session: requests.Session = None) -> List[Dict[str, Any]]:
    """
    Fetch all offerAccepted entities from The Graph subgraph with deterministic pagination.

    Approach:
    - Freeze a snapshot using _meta.block.number so results don't change during pagination.
    - Keep cursor-based pagination on `id` (same args / same return shape as your current function).

    Note:
    - This does NOT make results "chronological"; it only guarantees you won't miss/duplicate items
      because new events arrived while you were paging.
    """

    if "[api-key]" in url:
        url = url.replace("[api-key]", api_key)
    else:
        raise ValueError(
            "Invalid subgraph URL format. "
            "Expected '[api-key]' placeholder in the URL, e.g.:\n"
            "https://gateway.thegraph.com/api/[api-key]/subgraphs/id/<deployment_id>"
        )

    if session is None:
        session = requests.Session()

    headers = {"Content-Type": "application/json"}

    # Wait times in seconds between retries (2min, 6min, 10min, 15min)
    retry_delays = [120, 360, 600, 900]

    # Freeze snapshot block
    meta_query = """
    query {
      _meta { block { number } }
    }
    """
    for attempt, delay in enumerate(retry_delays + [None]):
        try:
            response = session.post(url, headers=headers, json={"query": meta_query}, timeout=30)
            response.raise_for_status()
            break
        except requests.exceptions.ConnectionError as e:
            if delay is None:
                raise
            logger.warning(f"Connection error on _meta query (attempt {attempt + 1}), retrying in {delay // 60} min... ({e})")
            time.sleep(delay)
            session = requests.Session()  # reset the session to force a fresh TCP connection and DNS resolution

    meta = response.json()
    if "errors" in meta:
        raise ValueError(f"GraphQL errors: {meta['errors']}")
    snapshot_block = meta.get("data", {}).get("_meta", {}).get("block", {}).get("number")
    if snapshot_block is None:
        raise ValueError("Could not read _meta.block.number from subgraph response.")

    # Subtract a small buffer from the snapshot block to ensure all indexers have processed it. Without this, indexers slightly behind the chain tip will return an error (missing block). 100 blocks ~ 500s on Gnosis Chain.
    snapshot_block -= 100

    all_offers: List[Dict[str, Any]] = []
    batch_size = 1000
    last_id = ""

    query_template = """
    query GetOfferAccepted($first: Int!, $lastId: String!, $block: Int!) {
      offerAccepteds(
        first: $first,
        where: { id_gt: $lastId },
        orderBy: id,
        orderDirection: asc,
        block: { number: $block }
      ) {
        id
        offerId
        offerToken
        buyerToken
        seller
        buyer
        price
        amount
        transactionHash
        logIndex
        blockNumber
        timestamp
      }
    }
    """

    while True:
        payload = {
            "query": query_template,
            "variables": {"first": batch_size, "lastId": last_id, "block": snapshot_block},
        }

        for attempt, delay in enumerate(retry_delays + [None]):
            try:
                response = session.post(url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                break
            except requests.exceptions.ConnectionError as e:
                if delay is None:
                    raise
                logger.warning(f"Connection error on pagination query (attempt {attempt + 1}), retrying in {delay // 60} min... ({e})")
                time.sleep(delay)
                session = requests.Session()  # reset the session to force a fresh TCP connection and DNS resolution

        data = response.json()

        if "errors" in data:
            raise ValueError(f"GraphQL errors: {data['errors']}")

        offers_batch = data.get("data", {}).get("offerAccepteds", [])
        if not offers_batch:
            break

        all_offers.extend(offers_batch)
        print(f"\rFetched {len(all_offers)} events offerAccepted from TheGraph...", end="", flush=True)

        last_id = offers_batch[-1]["id"]

        if len(offers_batch) < batch_size:
            break

    for offer in all_offers:
        offer["topic"] = "OfferAccepted"

    print()
    return all_offers