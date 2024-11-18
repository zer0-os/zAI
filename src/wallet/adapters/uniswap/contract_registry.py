import json
from pathlib import Path
from wallet.adapters.base_contract_config import ContractRegistry, ContractConfig

current_dir = Path(__file__).parent
with open(current_dir / "contract_abis" / "v3SwapRouter.json") as f:
    v3SwapRouter = json.load(f)
with open(current_dir / "contract_abis" / "v3Factory.json") as f:
    v3Factory = json.load(f)
with open(current_dir / "contract_abis" / "universalRouter.json") as f:
    universalRouter = json.load(f)
with open(current_dir / "contract_abis" / "pool.json") as f:
    pool = json.load(f)
with open(current_dir / "contract_abis" / "quoter.json") as f:
    quoter = json.load(f)
with open(current_dir / "contract_abis" / "permit2.json") as f:
    permit2 = json.load(f)


class UniswapContractRegistry(ContractRegistry):
    def __init__(self):
        super().__init__()
        self._configs = {
            "swap_router": ContractConfig(
                address="0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
                abi=v3SwapRouter,
            ),
            "factory": ContractConfig(
                address="0x1F98431c8aD98523631AE4a59f267346ea31F984",
                abi=v3Factory,
            ),
            "universal_router": ContractConfig(
                address="0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
                abi=universalRouter,
            ),
            "quoter": ContractConfig(
                address="0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
                abi=quoter,
            ),
            "permit2": ContractConfig(
                address="0x000000000022D473030F116dDEE9F6B43aC78BA3",
                abi=permit2,
            ),
            "pool": ContractConfig(
                address="0x0000000000000000000000000000000000000000",
                abi=pool,
            ),
        }


# Singleton instance
uniswap_contracts = UniswapContractRegistry()
