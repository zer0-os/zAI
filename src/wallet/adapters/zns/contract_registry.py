import json
from pathlib import Path
from wallet.adapters.base_contract_config import ContractRegistry, ContractConfig

current_dir = Path(__file__).parent
with open(current_dir / "contract_abis" / "ZNSRegistrar.json") as f:
    ZNSRegistrar = json.load(f)


class ZNSContractRegistry(ContractRegistry):
    def __init__(self):
        super().__init__()
        self._configs = {
            "registrar": ContractConfig(
                address="0x67611d0445f26a635a7D1cb87a3A687B95Ce4a05",
                abi=ZNSRegistrar,  # Add other ABI entries here
            ),
            "resolver": ContractConfig(
                address="0x...", abi=[...]  # Resolver address  # Resolver ABI
            ),
            "token": ContractConfig(
                address="0x...", abi=[...]  # Token address  # Token ABI
            ),
        }


# Singleton instance
zns_contracts = ZNSContractRegistry()
