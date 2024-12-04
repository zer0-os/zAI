from typing import TypedDict


class TokenInfo(TypedDict):
    """
    Type representing token information from LiFi API

    Attributes:
        address: Token contract address
        symbol: Token symbol (e.g., 'DAI')
        decimals: Number of decimals the token uses
        chainId: ID of the chain where token exists
        name: Full name of the token
        coinKey: Unique identifier for the token
        priceUSD: Current price in USD (optional)
        logoURI: URL to token logo image (optional)
    """

    address: str
    symbol: str
    decimals: int
    chainId: int
    name: str
    coinKey: str
    priceUSD: str | None
    logoURI: str | None


class TransactionRequest(TypedDict):
    """
    Type representing an ethers.js transaction request from LiFi API

    Attributes:
        data: The encoded contract call data
        to: The contract address to call
        value: The amount of native token to send (in hex)
        chainId: The chain ID where the transaction should be executed
        gasLimit: The maximum amount of gas to use (in hex)
        gasPrice: The gas price in wei (in hex)
    """

    data: str
    to: str
    value: str
    chainId: int
    gasLimit: str
    gasPrice: str
