from typing import Dict, List, Any
from web3.types import LogReceipt
from ._normalize_ethereum_address import normalize_ethereum_address

def _decode_log_offer_created(log: LogReceipt) -> Dict[str, Any]:
    """
    Decode an OfferCreated event log.
    
    Args:
        log: Raw OfferCreated event log
    
    Returns:
        Dictionary containing structured event data specific to this event type.
        See the documentation of get_and_decode_logs_yam.py for details on all returned fields.
    """
    # Extract data from event topics
    offer_token = normalize_ethereum_address(log['topics'][1].hex())
    buyer_token = normalize_ethereum_address(log['topics'][2].hex())
    offer_id = _hex_to_decimal(log['topics'][3].hex())
    
    hex_data = log['data'].hex()

    # Extract additional data from the data field
    seller_address = normalize_ethereum_address('0x' + hex_data[:64])
    buyer_address = normalize_ethereum_address('0x' + hex_data[64:128])
    price = _hex_to_decimal(hex_data[130:192])
    amount = _hex_to_decimal(hex_data[193:])

    # Create event data dictionary
    custom_data_log = {
        'seller': seller_address,
        'buyer': buyer_address,
        'price': price,
        'amount': amount,
        'offerToken': offer_token,
        'buyerToken': buyer_token,
        'offerId': offer_id,
        'topic': 'OfferCreated'
    }
    
    # Add standard log metadata
    custom_data_log.update(_get_generic_data_logs(log))

    return custom_data_log

def _decode_log_offer_accepted(log: LogReceipt) -> Dict[str, Any]:
    """
    Decode an OfferAccepted event log.
    
    Args:
        log: Raw OfferAccepted event log
    
    Returns:
        Dictionary containing structured event data specific to this event type.
        See the documentation of get_and_decode_logs_yam.py for details on all returned fields.
    """
    # Extract data from event topics
    offer_id = _hex_to_decimal(log['topics'][1].hex())
    seller_address = normalize_ethereum_address(log['topics'][2].hex())
    buyer_address = normalize_ethereum_address(log['topics'][3].hex())
    
    hex_data = log['data'].hex()

    # Extract additional data from the data field
    offer_token = normalize_ethereum_address('0x' + hex_data[:64])
    buyer_token = normalize_ethereum_address('0x' + hex_data[64:128])
    price = _hex_to_decimal(hex_data[128:192])
    amount = _hex_to_decimal(hex_data[192:256])

    # Create event data dictionary
    custom_data_log = {
        'seller': seller_address,
        'buyer': buyer_address,
        'price': price,
        'amount': amount,
        'offerToken': offer_token,
        'buyerToken': buyer_token,
        'offerId': offer_id,
        'topic': 'OfferAccepted'
    }
    
    # Add standard log metadata
    custom_data_log.update(_get_generic_data_logs(log))

    return custom_data_log

def _decode_log_offer_updated(log: LogReceipt) -> Dict[str, Any]:
    """
    Decode an OfferUpdated event log.
    
    Args:
        log: Raw OfferUpdated event log
    
    Returns:
        Dictionary containing structured event data specific to this event type.
        See the documentation of get_and_decode_logs_yam.py for details on all returned fields.
    """
    # Extract data from event topics
    offer_id = _hex_to_decimal(log['topics'][1].hex())
    new_price = _hex_to_decimal(log['topics'][2].hex())
    new_amount = _hex_to_decimal(log['topics'][3].hex())
    
    hex_data = log['data'].hex()

    # Extract additional data from the data field
    old_price = _hex_to_decimal(hex_data[:64])
    old_amount = _hex_to_decimal(hex_data[64:])

    # Create event data dictionary
    custom_data_log = {
        'oldPrice': old_price,
        'oldAmount': old_amount,
        'newPrice': new_price,
        'newAmount': new_amount,
        'offerId': offer_id,
        'topic': 'OfferUpdated'
    }

    # Add standard log metadata
    custom_data_log.update(_get_generic_data_logs(log))

    return custom_data_log

def _decode_log_offer_deleted(log: LogReceipt) -> Dict[str, Any]:
    """
    Decode an OfferDeleted event log.
    
    Args:
        log: Raw OfferDeleted event log
    
    Returns:
        Dictionary containing structured event data specific to this event type.
        See the documentation of get_and_decode_logs_yam.py for details on all returned fields.
    """
    # Extract data from event topics
    offer_id = _hex_to_decimal(log['topics'][1].hex())

    # Create event data dictionary
    custom_data_log = {
        'offerId': offer_id,
        'topic': 'OfferDeleted'
    }
    
    # Add standard log metadata
    custom_data_log.update(_get_generic_data_logs(log))

    return custom_data_log

def _get_generic_data_logs(log: LogReceipt) -> Dict[str, Any]:
    """
    Extract standard metadata common to all event logs.
    
    This function extracts the blockchain metadata that is common to all events,
    regardless of their specific type. Every decoded event will include these fields.
    
    Args:
        log: Raw event log
    
    Returns:
        Dictionary containing common log metadata:
        - transactionHash: Hash of the transaction
        - logIndex: Index of the log in the transaction
        - blockNumber: Block number where this event was emitted
    """
    return {
        'transactionHash': '0x' + log['transactionHash'].hex(),
        'logIndex': log['logIndex'],
        'blockNumber': log['blockNumber']
    }

def _hex_to_decimal(hex_str: str) -> int:
    #Convert a hexadecimal string to a decimal integer.
    return int(hex_str, 16)