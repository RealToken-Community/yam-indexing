from typing import Dict, List, Any, Optional
from web3 import Web3
from web3.types import LogReceipt
from .internals._decoders import _decode_log_offer_accepted, _decode_log_offer_deleted, _decode_log_offer_created, _decode_log_offer_updated

"""
YAM Contract Event Decoder

This module provides functions for fetching and decoding event logs (events) from YAM smart contracts
on the blockchain. It handles four types of events:
- OfferCreated
- OfferDeleted
- OfferAccepted
- OfferUpdated

All event decoders follow a common pattern:
- Extract data from the event topics and data field
- Structure the data into a dictionary specific to the event type
- Add common blockchain metadata using _get_generic_data_logs()

Usage Example:
    # Fetch raw logs from the blockchain
    raw_logs = get_raw_logs_yam(w3, contract_address, from_block, to_block)
    
    # Decode the logs into structured dictionaries
    decoded_logs = decode_raw_logs_yam(raw_logs)

Return Data Structure:
    Each decoded event is returned as a dictionary. All dictionaries contain some common keys,
    while others are specific to certain event types. Here is a comprehensive list of all
    possible keys that may appear in the returned dictionaries:
    
    Common keys (present in all event types):
    - topic: String indicating the event type ('OfferCreated', 'OfferDeleted', 'OfferAccepted', 'OfferUpdated')
    - transactionHash: String
    - logIndex: Integer
    - blockNumber: Integer
    - offerId: Integer
    
    Keys specific to OfferCreated and OfferAccepted events:
    - seller: String
    - buyer: String
    - price: Integer
    - amount: Integer
    - offerToken: String
    - buyerToken: String
    
    Keys specific to OfferUpdated events:
    - oldPrice: Integer
    - oldAmount: Integer
    - newPrice: Integer
    - newAmount: Integer
    
    OfferDeleted events only contain the common keys listed above.
"""

# Dictionary of YAM event topic hashes for efficient lookup
TOPIC_YAM = {
    'OfferCreated': '9fa2d733a579251ad3a2286bebb5db74c062332de37e4904aa156729c4b38a65',
    'OfferDeleted': '88686b85d6f2c3ab9a04e4f15a22fcfa025ffd97226dcf0a67cdf682def55676',
    'OfferAccepted': '0fe687b89794caf9729d642df21576cbddc748b0c8c7a5e1ec39f3a46bd00410',
    'OfferUpdated': 'c26a0a1f023ef119f120b3d9843d9e77dc8f66bbc0ea91d48d6dd39b8e351178'
}

def get_raw_logs_yam(w3: Web3, yam_contract_address: str, from_block: int, to_block: int) -> List[LogReceipt]:
    """
    Fetch raw event logs from a YAM contract within a specified block range.
    
    Args:
        w3: Web3 instance connected to an Ethereum node
        yam_contract_address: The address of the YAM contract
        from_block: Starting block number
        to_block: Ending block number or 'latest'
    
    Returns:
        List of raw log events
    """
    logs = w3.eth.get_logs({
        'address': yam_contract_address,
        'fromBlock': from_block,
        'toBlock': to_block
    })
    return logs

def decode_raw_logs_yam(logs: List[LogReceipt]) -> List[Optional[Dict[str, Any]]]:
    """
    Decode a list of raw YAM event logs into structured event data.
    
    Args:
        logs: List of raw log events from the YAM contract
    
    Returns:
        List of decoded events as dictionaries, with None for unrecognized events
    """
    decoded_logs = []
    for log in logs:
        topic_hash = log['topics'][0].hex()
        
        if topic_hash == TOPIC_YAM['OfferCreated']:
            event = _decode_log_offer_created(log)
        elif topic_hash == TOPIC_YAM['OfferDeleted']:
            event = _decode_log_offer_deleted(log)
        elif topic_hash == TOPIC_YAM['OfferAccepted']:
            event = _decode_log_offer_accepted(log)
        elif topic_hash == TOPIC_YAM['OfferUpdated']:
            event = _decode_log_offer_updated(log)
        else:
            continue  # Skip unrecognized events
        
        decoded_logs.append(event)

    return decoded_logs


from typing import List, Union
from web3 import Web3
from web3.types import LogReceipt

def get_raw_logs_yam_by_topic(
    w3: Web3,
    yam_contract_address: str,
    topics: Union[str, List[str]],
    from_block: int,
    to_block: int,
) -> List[LogReceipt]:
    """
    Fetch raw logs from YAM contract filtered by one or more topic0 values.
    """

    # Normalize to list
    if isinstance(topics, str):
        topics = [topics]

    # Ensure 0x prefix
    topics = [
        topic if topic.startswith("0x") else "0x" + topic
        for topic in topics
    ]

    logs = w3.eth.get_logs({
        "address": Web3.to_checksum_address(yam_contract_address),
        "fromBlock": from_block,
        "toBlock": to_block,
        "topics": [topics],
    })

    return logs