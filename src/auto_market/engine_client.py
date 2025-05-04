#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "hive-nectar",
#     "nectarengine",
#     "python-dotenv",
# ]
# ///

import argparse
import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv
from nectar import Hive
from nectar.wallet import Wallet
from nectarengine.market import Market
from nectarengine.wallet import Wallet as heWallet

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("duster")

# Configuration
DUST_THRESHOLD = 0  # Minimum balance to consider
UPPER_THRESHOLD = 1  # Maximum balance for dust collection

# This will be set based on command line arguments
# Using a dictionary as a mutable container to avoid global variable issues
config = {
    "dry_run": True,
    "target_token": "SWAP.HIVE",  # Default target token
}
WHITELIST = [
    "INCOME",
    "ARCHON",
    "ARCHONM",
    "ARMERO",
    "ONEUP",
    "BEE",
    "SIM",
    "PIMP",
    "PIZZA",
    "SWAP.HIVE",
    "SWAP.BTC",
    "SWAP.LTC",
    "SWAP.ETH",
]


@dataclass
class Token:
    symbol: str
    balance: float


class HiveConnection:
    """Manages connection to Hive and HiveEngine"""

    def __init__(self, active_wif: str, dry_run: bool = True):
        self.hive = Hive(keys=[active_wif], nodes="https://api.hive.blog", nobroadcast=dry_run)
        wallet = Wallet(blockchain_instance=self.hive)
        self.username = wallet.getAccountFromPrivateKey(active_wif)
        self.he_wallet = heWallet(account=self.username, blockchain_instance=self.hive)
        self.market = Market(blockchain_instance=self.hive)
        logger.info(f"🔑 Connected as: {self.username}")

    def get_balances(self) -> List[Token]:
        """Get token balances from HiveEngine"""
        raw_tokens = self.he_wallet.get_balances()
        return [Token(symbol=t["symbol"], balance=float(t["balance"])) for t in raw_tokens]

    def get_orderbook_top(self, symbol: str) -> tuple[float, float]:
        """Fetch the highest bid and lowest ask for a token"""
        highest_bid = 0
        lowest_ask = 0

        # Get buy book (bids)
        buy_book = self.market.get_buy_book(symbol, limit=1)
        if buy_book and len(buy_book) > 0:
            highest_bid = float(buy_book[0].get("price", 0))

        # Get sell book (asks)
        sell_book = self.market.get_sell_book(symbol, limit=1)
        if sell_book and len(sell_book) > 0:
            lowest_ask = float(sell_book[0].get("price", 0))

        return highest_bid, lowest_ask

    def sell_token(self, symbol: str, amount: float, price: float) -> bool:
        """Sell a token on the market"""
        try:
            # The Market.sell method signature is: sell(account, amount, symbol, price)
            self.market.sell(self.username, amount, symbol, price)
            logger.info(f"✅ Sell order placed for {amount} {symbol} at {price}")
            return True
        except Exception as e:
            logger.error(f"❌ Error selling {symbol}: {str(e)}")
            return False

    def transfer_token(
        self,
        to_account: str,
        symbol: str,
        amount: float,
        memo: str = "Automatic transfer",
    ) -> bool:
        """Transfer a token to another account"""
        try:
            self.he_wallet.transfer(to_account, amount, symbol, memo=memo)
            return True
        except Exception as e:
            logger.error(f"❌ Error transferring {symbol}: {str(e)}")
            return False

    def buy_token(self, symbol: str, amount: float, price: float) -> bool:
        """Buy a token from the market"""
        try:
            # The Market.buy method signature is: buy(account, amount, symbol, price)
            self.market.buy(self.username, amount, symbol, price)
            logger.info(f"✅ Buy order placed for {amount} {symbol} at {price}")
            return True
        except Exception as e:
            logger.error(f"❌ Error buying {symbol}: {str(e)}")
            return False


class TokenProcessor:
    """Base class for token processing strategies"""

    def __init__(self, connection: HiveConnection):
        self.connection = connection

    def filter_tokens(self, tokens: List[Token]) -> List[Token]:
        """Filter tokens based on strategy"""
        raise NotImplementedError("Subclasses must implement filter_tokens")

    def process_tokens(self, tokens: List[Token]) -> None:
        """Process tokens based on strategy"""
        filtered_tokens = self.filter_tokens(tokens)
        total_steps = len(filtered_tokens)

        if total_steps == 0:
            logger.info("No tokens to process")
            return

        logger.info(f"Found {total_steps} tokens to process")

        for i, token in enumerate(filtered_tokens):
            self.process_token(token)
            logger.info(f"Progress: {i + 1}/{total_steps} ({int((i + 1) / total_steps * 100)}%)")

        self.on_completion()

    def process_token(self, token: Token) -> None:
        """Process a single token"""
        raise NotImplementedError("Subclasses must implement process_token")

    def on_completion(self) -> None:
        """Called when all tokens have been processed"""
        pass


class DustCollector(TokenProcessor):
    """Collects dust tokens and sells them for the target token"""

    def filter_tokens(self, tokens: List[Token]) -> List[Token]:
        return [
            token
            for token in tokens
            if token.symbol not in WHITELIST
            and token.balance > DUST_THRESHOLD
            and token.balance < UPPER_THRESHOLD
        ]

    def process_token(self, token: Token) -> None:
        logger.info(f"🔹 Selling {token.balance} {token.symbol}...")
        highest_bid, _ = self.connection.get_orderbook_top(token.symbol)

        if highest_bid > 0:
            if not config["dry_run"]:
                self.connection.sell_token(token.symbol, token.balance, highest_bid)
            else:
                logger.info(f"[DRY RUN] Would sell {token.balance} {token.symbol} at {highest_bid}")
            # Wait for order to process
            time.sleep(4)
        else:
            logger.warning(f"⚠️ No buyers for {token.symbol}, skipping.")

    def on_completion(self) -> None:
        # If target_token is not SWAP.HIVE, buy the target token with accumulated SWAP.HIVE
        target_token = config["target_token"]
        if target_token != "SWAP.HIVE":
            logger.info(f"🟢 Buying {target_token} with accumulated SWAP.HIVE...")

            # Get updated SWAP.HIVE balance
            tokens = self.connection.get_balances()
            hive_token = next((t for t in tokens if t.symbol == "SWAP.HIVE"), None)

            if hive_token and hive_token.balance > DUST_THRESHOLD:
                # Get the lowest ask price for the target token
                _, lowest_ask = self.connection.get_orderbook_top(target_token)

                if lowest_ask > 0:
                    if not config["dry_run"]:
                        self.connection.buy_token(target_token, hive_token.balance, lowest_ask)
                    else:
                        logger.info(
                            f"[DRY RUN] Would buy {target_token} using {hive_token.balance} SWAP.HIVE at {lowest_ask}"
                        )
                else:
                    logger.warning(f"⚠️ No {target_token} available for purchase.")
            else:
                logger.warning(f"⚠️ Not enough SWAP.HIVE to buy {target_token}.")

        logger.info("🎯 Dust Collection Complete!")


class TokenTransferer(TokenProcessor):
    """Transfers dust tokens to another account"""

    def __init__(self, connection: HiveConnection, destination: str):
        super().__init__(connection)
        self.destination = destination

    def filter_tokens(self, tokens: List[Token]) -> List[Token]:
        return [
            token
            for token in tokens
            if token.symbol not in WHITELIST and token.balance > 0 and token.balance < 1
        ]

    def process_token(self, token: Token) -> None:
        logger.info(f"Transferring {token.balance} {token.symbol} to {self.destination}")
        if not config["dry_run"]:
            self.connection.transfer_token(self.destination, token.symbol, token.balance)
        else:
            logger.info(
                f"[DRY RUN] Would transfer {token.balance} {token.symbol} to {self.destination}"
            )
        time.sleep(1)

    def on_completion(self) -> None:
        logger.info(f"🎯 All transfers to {self.destination} complete!")


class AllTokenSeller(TokenProcessor):
    """Sells all tokens (except whitelisted) for the target token"""

    def filter_tokens(self, tokens: List[Token]) -> List[Token]:
        return [
            token
            for token in tokens
            if token.symbol != config["target_token"]
            and token.symbol not in WHITELIST
            and token.balance > 0
        ]

    def process_token(self, token: Token) -> None:
        logger.info(f"🔹 Selling {token.balance} {token.symbol}...")
        highest_bid, _ = self.connection.get_orderbook_top(token.symbol)

        if highest_bid > 0:
            if not config["dry_run"]:
                self.connection.sell_token(token.symbol, token.balance, highest_bid)
            else:
                logger.info(f"[DRY RUN] Would sell {token.balance} {token.symbol} at {highest_bid}")
            # Wait for order to process
            time.sleep(4)
        else:
            logger.warning(f"⚠️ No buyers for {token.symbol}, skipping.")

    def on_completion(self) -> None:
        logger.info(f"🎯 All tokens sold for {config['target_token']}!")


def setup_connection() -> Optional[HiveConnection]:
    """Set up connection to Hive and HiveEngine"""
    load_dotenv()
    active_wif = os.getenv("ACTIVE_WIF")

    if not active_wif:
        logger.error("❌ No active key found in .env file")
        return None

    return HiveConnection(active_wif, config["dry_run"])


def collect_dust():
    """Collect dust tokens and sell them for SWAP.HIVE"""
    connection = setup_connection()
    if not connection:
        return

    tokens = connection.get_balances()
    collector = DustCollector(connection)
    collector.process_tokens(tokens)


def transfer_dust(destination=None):
    """Transfer dust tokens to another account"""
    connection = setup_connection()
    if not connection:
        return

    if not destination:
        destination = input("Enter destination account: ")
        if not destination:
            logger.error("No destination specified")
            return

    tokens = connection.get_balances()
    transferer = TokenTransferer(connection, destination)
    transferer.process_tokens(tokens)


def sell_everything():
    """Sell all tokens except whitelisted ones for SWAP.HIVE"""
    connection = setup_connection()
    if not connection:
        return

    tokens = connection.get_balances()
    seller = AllTokenSeller(connection)
    seller.process_tokens(tokens)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Hive Engine token management tool",
        epilog=f"By default, collects dust tokens (< {UPPER_THRESHOLD}) and sells them for {config['target_token']}",
    )

    # Create a mutually exclusive group for the main actions
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "-c",
        "--collect",
        action="store_true",
        help=f"Collect dust tokens (< {UPPER_THRESHOLD} balance) and sell for {config['target_token']}",
    )
    action_group.add_argument(
        "-t",
        "--transfer",
        metavar="ACCOUNT",
        help="Transfer dust tokens to specified account",
    )
    action_group.add_argument(
        "-s",
        "--sell-all",
        action="store_true",
        help=f"Sell ALL tokens (except whitelisted ones) for {config['target_token']}",
    )

    # Add option to disable dry run mode
    parser.add_argument(
        "-e",
        "--execute",
        action="store_true",
        help="Execute transactions (disable dry run mode)",
    )

    # Add option to specify target token
    parser.add_argument(
        "-T",
        "--target-token",
        metavar="TOKEN",
        help=f"Target token to buy (default: {config['target_token']})",
    )

    # Parse arguments
    args = parser.parse_args()

    # Set dry run mode based on args
    if args.execute:
        config["dry_run"] = False
        logger.info("LIVE MODE: Transactions will be executed")
    else:
        logger.info("DRY RUN MODE: No transactions will be executed")

    # Set target token if specified
    if args.target_token:
        config["target_token"] = args.target_token
        logger.info(f"Target token set to: {config['target_token']}")

    # Determine which action to take
    if args.transfer:
        # Transfer dust tokens to specified account
        connection = setup_connection()
        if connection:
            tokens = connection.get_balances()
            transferer = TokenTransferer(connection, args.transfer)
            transferer.process_tokens(tokens)
    elif args.sell_all:
        # Sell all non-whitelisted tokens
        sell_everything()
    else:
        # Default action: collect dust
        collect_dust()
