import requests
from typing import List, Dict, Any


def fetch_all_offer_created(api_key: str, url: str) -> List[Dict[str, Any]]:
    """
    Fetch all offerCreated entities from The Graph subgraph with deterministic pagination.

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

    headers = {"Content-Type": "application/json"}

    # Freeze snapshot block
    meta_query = """
    query {
      _meta { block { number } }
    }
    """
    response = requests.post(url, headers=headers, json={"query": meta_query}, timeout=30)
    response.raise_for_status()
    meta = response.json()
    if "errors" in meta:
        raise ValueError(f"GraphQL errors: {meta['errors']}")
    snapshot_block = meta.get("data", {}).get("_meta", {}).get("block", {}).get("number")
    if snapshot_block is None:
        raise ValueError("Could not read _meta.block.number from subgraph response.")

    all_offers: List[Dict[str, Any]] = []
    batch_size = 1000
    last_id = ""

    query_template = """
    query GetOfferCreated($first: Int!, $lastId: String!, $block: Int!) {
      offerCreateds(
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

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise ValueError(f"GraphQL errors: {data['errors']}")

        offers_batch = data.get("data", {}).get("offerCreateds", [])
        if not offers_batch:
            break

        all_offers.extend(offers_batch)
        print(f"\rFetched {len(all_offers)} events offerCreated from TheGraph...", end="", flush=True)

        last_id = offers_batch[-1]["id"]

        if len(offers_batch) < batch_size:
            break

    for offer in all_offers:
        offer["topic"] = "OfferCreated"

    print()
    return all_offers
