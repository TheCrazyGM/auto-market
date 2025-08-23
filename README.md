# auto-market

Automate market operations for multiple Hive accounts using a single authority account. This package provides two command-line tools:

- `hive-market`: Trade HBD/HIVE on the internal market, plus stake HBD to savings and power up HIVE
- `engine-market`: Sell tokens on the Hive-Engine sidechain market

## Features

- Buy/Sell HBD for HIVE on the internal Hive market
- Stake HBD to Savings (move HBD to savings)
- Power Up HIVE to Vesting (convert liquid HIVE to HP)
- Buy/Sell tokens on the Hive-Engine sidechain market
- Process multiple accounts using a single active key
- Sell specific tokens or all non-whitelisted tokens
- Configure token whitelist in the YAML configuration file
- Set minimum and maximum amounts for trading
- Dry-run mode to simulate transactions without broadcasting
- Colored logging and console output with Rich (detailed logging with debug option)

## Command-line Arguments

### hive-market

```bash
hive-market [--active-key ACTIVE_KEY] [--debug] [--dry-run] [--accounts PATH] \
           [--min-amount AMOUNT] [--max-amount AMOUNT] \
           [--operation {sell,buy,stake,powerup}] [--memo MEMO]
```

| Argument          | Type  | Description                                                                              |
| ----------------- | ----- | ---------------------------------------------------------------------------------------- |
| `-k/--active-key` | str   | Active key for the main account. If omitted, uses ACTIVE_WIF env variable or YAML.       |
| `-d/--debug`      | flag  | Enable debug logging.                                                                    |
| `--dry-run`       | flag  | Simulate operations without broadcasting transactions.                                   |
| `-a/--accounts`   | str   | Path to YAML file with accounts and/or active key. Defaults to accounts.yaml.            |
| `-m/--min-amount` | float | Minimum amount threshold to trigger the operation (default: 0.001).                      |
| `-x/--max-amount` | float | Maximum amount to use in one run (default: no limit).                                    |
| `-o/--operation`  | str   | Operation mode: `sell`, `buy`, `stake` (HBD to savings), or `powerup` (HIVE to vesting). |
| `--memo`          | str   | Memo for staking to savings (used only with `--operation stake`).                        |

### engine-market

```bash
engine-market [--active-key ACTIVE_KEY] [--debug] [--dry-run] [--accounts PATH] [--token SYMBOL] [--all-tokens] [--min-amount AMOUNT] [--max-amount AMOUNT] [--target TOKEN] [--operation MODE]
```

| Argument          | Type  | Description                                                                        |
| ----------------- | ----- | ---------------------------------------------------------------------------------- |
| `-k/--active-key` | str   | Active key for the main account. If omitted, uses ACTIVE_WIF env variable or YAML. |
| `-d/--debug`      | flag  | Enable debug logging.                                                              |
| `--dry-run`       | flag  | Simulate trading without broadcasting transactions.                                |
| `-a/--accounts`   | str   | Path to YAML file with accounts and/or active key. Defaults to accounts.yaml.      |
| `-t/--token`      | str   | Token symbol to trade (e.g., LEO, POB). Not required if --all-tokens is used.      |
| `-A/--all-tokens` | flag  | Sell all tokens except those in the whitelist (only for sell operation).           |
| `-m/--min-amount` | float | Minimum token amount to trigger a trade (default: 0.00001).                        |
| `-x/--max-amount` | float | Maximum token amount to trade in one run (default: no limit).                      |
| `--target`        | str   | Target token to trade with (default: SWAP.HIVE).                                   |
| `-o/--operation`  | str   | Trading operation mode: 'sell' (default) or 'buy'.                                 |

## 🛠️ Installation

```bash
# Clone the repo
$ git clone https://github.com/thecrazygm/auto-market.git
$ cd auto-market

# Install in editable mode (recommended for development)
$ uv sync
# or
$ pip install -e .
```

## 📄 Configuration

The package can be configured using a YAML file. By default, it looks for `accounts.yaml` in the current directory, but you can specify a different file using the `-a/--accounts` argument.

Example `accounts.yaml`:

```yaml
# Hive accounts configuration for auto-market tool
# The first account in the list will be used as the authority account

# List of accounts to process
accounts:
  - yourmainaccount # This account's active key will be used
  - secondaccount # Will use yourmainaccount's authority
  - thirdaccount # Will use yourmainaccount's authority

# Active key for the authority account (first in the list)
# Can also be provided via --active-key CLI argument or ACTIVE_WIF environment variable
# active_key: YOUR_ACTIVE_KEY_HERE

# Hive-Engine token whitelist
# These tokens will not be sold when using the --all-tokens option
whitelist:
  - SWAP.HIVE
  - SWAP.BTC
  - SWAP.ETH
  - INCOME
  - BEE
  - LEO
```

## 💃 Usage Examples

### Trading HBD for HIVE and Account Ops

After installation, you can use either the command-line scripts or the Python modules directly.

#### Using Command-line Scripts (Hive)

```bash
# Sell HBD for HIVE (uses accounts.yaml by default)
hive-market --active-key YOUR_ACTIVE_KEY --operation sell

# Buy HBD with HIVE
hive-market --active-key YOUR_ACTIVE_KEY --operation buy

# Stake HBD to savings for each account (with memo)
hive-market --active-key YOUR_ACTIVE_KEY --operation stake --memo "auto to savings"

# Power up available HIVE to vesting (HP) for each account
hive-market --active-key YOUR_ACTIVE_KEY --operation powerup

# Minimum and maximum thresholds (applies to sell/buy/stake/powerup accordingly)
hive-market --min-amount 10.0 --max-amount 100.0 --operation sell

# Dry run (simulate without broadcasting)
hive-market --dry-run --operation powerup

# Use a specific accounts configuration file
hive-market --accounts /path/to/your/config.yaml --operation stake

# Enable debug logging
hive-market --debug --operation buy
```

#### Using Python Modules (Hive)

```bash
# Basic usage
python -m auto_market.hive_market --active-key YOUR_ACTIVE_KEY
```

### Trading Hive-Engine Tokens

#### Using Command-line Scripts (Hive-Engine)

```bash
# Sell a specific token
engine-market --token LEO --min-amount 1.0 --operation sell

# Buy a specific token
engine-market --token LEO --min-amount 1.0 --operation buy

# Sell all non-whitelisted tokens
engine-market --all-tokens --operation sell

# Specify target token to trade with (default is SWAP.HIVE)
engine-market --token CTP --target SWAP.BTC

# Dry run (simulate without broadcasting)
engine-market --token POB --dry-run

# Use a specific accounts configuration file
engine-market --all-tokens --accounts /path/to/your/config.yaml
```

#### Using Python Modules (Hive-Engine)

```bash
# Sell a specific token
python -m auto_market.he_market --token LEO --operation sell

# Buy a specific token
python -m auto_market.he_market --token LEO --operation buy

# Sell all non-whitelisted tokens
python -m auto_market.he_market --all-tokens --operation sell
```

## 🔐 Security

The active key is sensitive information. You have several options to provide it:

1. Store it in the `accounts.yaml` file (least secure)
2. Provide it via the `--active-key` command-line argument
3. Set it as an environment variable `ACTIVE_WIF`

For production use, option 3 is recommended.

## 🗂️ Project Structure

```bash
auto-market/
├── src/
│   └── auto_market/
│       ├── __init__.py         # Package version information
│       ├── config.py           # Configuration handling
│       ├── hive_client.py      # Hive blockchain operations
│       ├── he_client.py        # Hive-Engine blockchain operations
│       ├── he_market.py        # Hive-Engine token selling script
│       ├── logging_setup.py    # Logging configuration
│       └── hive_market.py      # Hive CLI: trade HBD/HIVE, stake HBD to savings, power up HIVE
├── pyproject.toml
├── README.md
└── ...
```

## 📝 Contributing & Linting

- Code style and linting are enforced by Ruff. Run `ruff check .` and `ruff format .` before submitting PRs.
- All configuration is in `pyproject.toml`.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ❤️ Thanks & Credits

- [hive-nectar](https://github.com/thecrazygm/hive-nectar/) - Python library for Hive blockchain interactions
- [nectarengine](https://github.com/thecrazygm/nectarengine) - Python library for Hive-Engine interactions
- Built with [Hatchling](https://hatch.pypa.io/latest/)
- Of course [uv](https://docs.astral.sh/uv/) and [Ruff](https://docs.astral.sh/ruff/) for the amazing python tools.
- Maintained by Michael Garcia (@thecrazygm).
