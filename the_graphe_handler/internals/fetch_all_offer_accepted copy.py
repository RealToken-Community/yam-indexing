import requests
from typing import List, Dict, Any

def fetch_all_offer_accepted(api_key: str, url: str) -> List[Dict[str, Any]]:
    """
    Fetch all offerAccepted entities from The Graph subgraph with cursor-based pagination.
    
    Arg:
        api_key (str): The Graph API key for authentication
        url (str): The subgraph url to query
    
    Returns:
        List[Dict[str, Any]]: Complete list of all offerAccepted entities
    
    Raises:
        requests.RequestException: If API request fails
        ValueError: If response format is unexpected
    """


    
    if "[api-key]" in url:
        url = url.replace("[api-key]", api_key)
    else:
        raise ValueError(
            "Invalid subgraph URL format. "
            "Expected '[api-key]' placeholder in the URL, e.g.:\n"
            "https://gateway.thegraph.com/api/[api-key]/subgraphs/id/<deployment_id>"
        )
    

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    all_offers = []
    batch_size = 1000
    last_id = ""  # For cursor-based pagination
    
    # GraphQL query using cursor-based pagination (where clause)
    query_template = """
    query GetOfferAccepted($first: Int!, $lastId: String!) {
        offerAccepteds(
            first: $first,
            where: { id_gt: $lastId },
            orderBy: id,
            orderDirection: asc
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
        # Prepare the GraphQL request
        payload = {
            "query": query_template,
            "variables": {
                "first": batch_size,
                "lastId": last_id
            }
        }
         
        # Make the request
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        
        # Check for GraphQL errors
        if "errors" in data:
            raise ValueError(f"GraphQL errors: {data['errors']}")
        
        # Extract the offers from this batch
        offers_batch = data.get("data", {}).get("offerAccepteds", [])
        
        if not offers_batch:
            break
        
        # Add to our complete list
        all_offers.extend(offers_batch)

        # Update progress counter (overwrite previous number)
        print(f"\rFetched {len(all_offers)} events offerAccepted from TheGraph...", end="", flush=True)
        
        # Update the cursor (last ID) for next batch
        last_id = offers_batch[-1]["id"]
        
        # If we got less than the batch size, we've reached the end
        if len(offers_batch) < batch_size:
            break
    
    for i, offer in enumerate(all_offers):
        all_offers[i]['topic'] = 'OfferAccepted'

    return all_offers
