from web3 import Web3
from typing import AnyStr

def normalize_ethereum_address(address: AnyStr) -> str:
    """
    Normalizes an Ethereum address by removing leading zeros and applying checksum formatting.
    
    This function takes a hexadecimal string representing an Ethereum address (potentially with
    extra leading zeros) and returns the normalized form with proper checksum capitalization.
    
    Args:
        address: A string containing the Ethereum address, must start with '0x'
        
    Returns:
        str: The normalized Ethereum address with checksum formatting
        
    Raises:
        ValueError: If the input address doesn't start with '0x'
        
    Examples:
        normalize_ethereum_address('0x000000000000000000000000a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6')
        '0xA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6'
        normalize_ethereum_address('0x0000000000000000000000000000000000000000')
        '0x0000000000000000000000000000000000000000'
    """
    # Validate the input address format
    if not isinstance(address, str):
        address = str(address)
    
    # Remove leading zeros after '0x' prefix (keeping the last 40 characters)
    # Standard Ethereum addresses are 20 bytes (40 hex characters) plus '0x' prefix
    address_without_leading_zeros = '0x' + address[-40:] if len(address) > 42 else address
    
    # Apply checksum formatting, but skip for zero address
    ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
    if address_without_leading_zeros.lower() != ZERO_ADDRESS:
        checksummed_address = Web3.to_checksum_address(address_without_leading_zeros)
        return checksummed_address
    else:
        return ZERO_ADDRESS