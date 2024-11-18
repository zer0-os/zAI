from typing import List, Optional, Dict, Any

from wallet.exceptions import InvalidAddressError
from wallet.adapters.base_adapter import BaseAdapter, MethodDescriptor
from dataclasses import dataclass
from decimal import Decimal
from wallet.adapters.zns.contract_registry import zns_contracts


@dataclass
class DistributionConfig:
    """Configuration for domain distribution settings"""

    enabled: bool
    price_config: Dict[str, Any]  # ICurvePriceConfig
    payment_type: int
    stake_fee: int
    min_duration: int
    max_duration: int


@dataclass
class PaymentConfig:
    """Configuration for domain payment settings"""

    payment_type: int
    stake_fee: int
    min_duration: int
    max_duration: int


class ZNSAdapter(BaseAdapter):
    """
    Adapter for interacting with Zero Name Service (ZNS) protocol.
    Provides functionality for domain registration, management, and resolution.
    """

    def __init__(self, wallet):
        super().__init__(wallet)
        zns_contracts.initialize(self._wallet._web3)

    async def register_domain(
        self,
        domain_name: str,
        duration: int,
        domain_address: Optional[str] = None,
        token_uri: Optional[str] = None,
        distribution_config: Optional[DistributionConfig] = None,
        payment_config: Optional[PaymentConfig] = None,
    ) -> str:
        """
        Register a new domain on ZNS.

        Args:
            domain_name: Name of the domain to register (e.g. "wilder")
            duration: Registration duration in seconds
            domain_address: Optional address for the domain to resolve to
            token_uri: Optional URI for the domain's NFT metadata
            distribution_config: Optional configuration for domain distribution
            payment_config: Optional configuration for payment settings

        Returns:
            str: Transaction hash of the registration

        Raises:
            TransactionError: If the registration fails
            InvalidAddressError: If domain_address is invalid
        """
        # Validate domain address if provided
        if domain_address and not self._wallet._web3.is_address(domain_address):
            raise InvalidAddressError(f"Invalid domain address: {domain_address}")

        # Get contract instance
        registrar_contract = zns_contracts.get_contract("registrar")

        # Prepare transaction parameters
        tx_params = {
            "name": domain_name,
            "domainAddress": domain_address
            or "0x0000000000000000000000000000000000000000",
            "tokenURI": token_uri or "",
            "distributionConfig": self._prepare_distribution_config(
                distribution_config
            ),
            "paymentConfig": self._prepare_payment_config(payment_config),
        }

        try:
            # Build transaction
            tx = registrar_contract.functions.registerRootDomain(
                **tx_params
            ).build_transaction(
                {
                    "from": self._wallet._account.address,
                    "nonce": self._wallet._web3.eth.get_transaction_count(
                        self._wallet._account.address
                    ),
                }
            )

            # Sign and send transaction
            signed_tx = self._wallet._web3.eth.account.sign_transaction(
                tx, self._wallet._account.key
            )
            tx_hash = self._wallet._web3.eth.send_raw_transaction(
                signed_tx.raw_transaction
            )

            # Wait for transaction receipt
            receipt = self._wallet._web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt["status"] != 1:
                raise TransactionError("Domain registration failed")

            return receipt["transactionHash"].hex()

        except Exception as e:
            raise TransactionError(f"Failed to register domain: {str(e)}")

    def _prepare_distribution_config(
        self, config: Optional[DistributionConfig]
    ) -> Dict[str, Any]:
        """Prepare distribution config for contract call"""
        if not config:
            return {
                "enabled": False,
                "priceConfig": {
                    "basePrice": 0,
                    "priceMultiplier": 0,
                    "priceDivisor": 0,
                },
                "paymentType": 0,
                "stakeFee": 0,
                "minDuration": 0,
                "maxDuration": 0,
            }
        return {
            "enabled": config.enabled,
            "priceConfig": config.price_config,
            "paymentType": config.payment_type,
            "stakeFee": config.stake_fee,
            "minDuration": config.min_duration,
            "maxDuration": config.max_duration,
        }

    def _prepare_payment_config(
        self, config: Optional[PaymentConfig]
    ) -> Dict[str, Any]:
        """Prepare payment config for contract call"""
        if not config:
            return {"paymentType": 0, "stakeFee": 0, "minDuration": 0, "maxDuration": 0}
        return {
            "paymentType": config.payment_type,
            "stakeFee": config.stake_fee,
            "minDuration": config.min_duration,
            "maxDuration": config.max_duration,
        }

    async def resolve_address(self, domain_name: str) -> str:
        """
        Resolve a domain name to its associated address.

        Args:
            domain_name: Domain name to resolve

        Returns:
            str: Resolved address
        """
        # Implementation will interact with ZNSAddressResolver contract
        pass

    async def set_resolver(self, domain_name: str, resolver_address: str) -> bool:
        """
        Set a resolver for a domain.

        Args:
            domain_name: Domain name to update
            resolver_address: Address of the resolver contract

        Returns:
            bool: Success status
        """
        # Implementation will interact with ZNSRegistry contract
        pass

    async def transfer_domain(self, domain_name: str, to_address: str) -> bool:
        """
        Transfer domain ownership to another address.

        Args:
            domain_name: Domain name to transfer
            to_address: Recipient address

        Returns:
            bool: Success status
        """
        # Implementation will interact with ZNSDomainToken contract
        pass
