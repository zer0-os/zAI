import json
from pathlib import Path
from wallet.adapters.base_contract_config import ContractRegistry, ContractConfig

current_dir = Path(__file__).parent

# Load ABIs
with open(current_dir / "contract_abis" / "erc20.json") as f:
    ERC20_ABI = json.load(f)

with open(current_dir / "contract_abis" / "erc721.json") as f:
    ERC721_ABI = json.load(f)

with open(current_dir / "contract_abis" / "erc1155.json") as f:
    ERC1155_ABI = json.load(f)

with open(current_dir / "contract_abis" / "weth.json") as f:
    WETH_ABI = json.load(f)


class CommonContractRegistry(ContractRegistry):
    def __init__(self):
        super().__init__()
        self._abis = {
            "erc20": ERC20_ABI,
            "erc721": ERC721_ABI,
            "erc1155": ERC1155_ABI,
            "weth": WETH_ABI,
        }
        self._configs = {
            "erc20": ContractConfig(
                address="0x0000000000000000000000000000000000000000",
                abi=self._abis["erc20"],
            ),
            "erc721": ContractConfig(
                address="0x0000000000000000000000000000000000000000",
                abi=self._abis["erc721"],
            ),
            "erc1155": ContractConfig(
                address="0x0000000000000000000000000000000000000000",
                abi=self._abis["erc1155"],
            ),
            "weth": ContractConfig(
                address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                abi=self._abis["weth"],
            ),
        }


# Singleton instance
common_contracts = CommonContractRegistry()
