class WalletError(Exception):
    """Base exception for wallet-related errors."""
    pass

class InsufficientBalanceError(WalletError):
    """Raised when wallet has insufficient balance for operation."""
    pass

class TransactionError(WalletError):
    """Raised when a transaction fails."""
    pass

class InvalidAddressError(WalletError):
    """Raised when an invalid address is provided."""
    pass

class AdapterError(WalletError):
    """Base exception for adapter-related errors"""
    pass

class AdapterNotFoundError(AdapterError):
    """Raised when attempting to access an unregistered adapter"""
    pass

class AdapterConflictError(AdapterError):
    """Raised when there's a namespace conflict between adapters"""
    pass 