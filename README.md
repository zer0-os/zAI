# AI Agent

## Creating an encrypted Ethereum key file

### Installing Geth

First, install Geth (Go Ethereum) using the following commands:
```bash
sudo add-apt-repository -y ppa:ethereum/ethereum
sudo apt-get update
sudo apt-get install geth
```


### Creating a New Account
To create a new Ethereum account and keyfile:
```bash
geth account new
```

This command will:
1. Prompt you to enter a password
2. Generate a new keyfile in the default directory (`~/.ethereum/keystore/`)
3. Output your new account address

> **Note**: Keep your password and keyfile secure. Loss of either will result in loss of access to your account.

This keyfile can be used as the `key_path` parameter in the `ZWallet` class.
If no key_path is provided, the default path will be used: `./keyfile`
```python
wallet = ZWallet(key_path='~/.ethereum/keystore/<keyfile>')
```

Set your keyfile password in the `.env` file:
```
KEY_PASSWORD=<your_password>
```

You will also need to set the following environment variables:

```
RPC_URL
OPENAI_API_KEY
```

## Running the agent

```bash
poetry install
poetry run agent
```

## Capabilities

- Receive tokens to the agent controlled wallet
- Check wallet balance
- Transfer tokens
- Swap tokens on Uniswap V3