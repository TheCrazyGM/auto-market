"""
Hive-Engine blockchain connectivity module.
Provides classes and functions for connecting to the Hive-Engine blockchain and performing token operations.
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from nectar import Hive
from nectarengine.market import Market
from nectarengine.wallet import Wallet as HeWallet

logger = logging.getLogger(__name__)


@dataclass
class Token:
    """Represents a Hive-Engine token with its balance"""

    symbol: str
    balance: float


def connect_to_hive_engine(hive: Hive, account_name: str) -> Tuple[HeWallet, Market]:
    """
    Initialize Hive-Engine wallet and market using an existing Hive connection.

    Args:
        hive: An existing Hive blockchain instance.
        account_name: The account name to use for the Hive-Engine wallet.

    Returns:
        Tuple of (Hive-Engine wallet, Hive-Engine market)

    Raises:
        Exception: If connection fails.
    """
    try:
        logger.debug(f"Initializing Hive-Engine for account: {account_name}")

        # Initialize Hive-Engine wallet and market
        he_wallet = HeWallet(account=account_name, blockchain_instance=hive)
        market = Market(blockchain_instance=hive)

        logger.debug("Hive-Engine initialized successfully")
        return he_wallet, market
    except Exception as e:
        logger.error(f"Failed to initialize Hive-Engine: {e}")
        raise


class HiveEngineTrader:
    """
    Class for handling Hive-Engine market trading operations.
    Supports both selling tokens for SWAP.HIVE and buying tokens with SWAP.HIVE.
    """

    def __init__(self, hive: Hive, account_name: str, min_token_amount: float, max_token_amount: Optional[float] = None):
        """
        Initialize Hive-Engine trading instance.

        Args:
            hive: Connected Hive blockchain instance
            account_name: The account name to use for operations
            min_token_amount: Minimum token balance to trigger a trade operation
            max_token_amount: Maximum token amount to trade in one transaction (None = no limit)
        """
        logger.debug(
            f"Initializing HiveEngineTrader for {account_name} with min_token_amount={min_token_amount}, max_token_amount={max_token_amount}"
        )
        self.hive = hive
        self.account_name = account_name
        self.min_token_amount = min_token_amount
        self.max_token_amount = max_token_amount
        self.dry_run = hive.nobroadcast

        # Initialize Hive-Engine wallet and market
        self.wallet, self.market = connect_to_hive_engine(hive, account_name)
        logger.debug("HiveEngineTrader initialized successfully")

    def get_token_balances(self) -> List[Token]:
        """
        Get token balances from Hive-Engine for the connected account.

        Returns:
            List of Token objects with symbol and balance.
        """
        try:
            raw_tokens = self.wallet.get_balances()
            tokens = [Token(symbol=t["symbol"], balance=float(t["balance"])) for t in raw_tokens]
            logger.debug(f"Retrieved {len(tokens)} token balances")
            return tokens
        except Exception as e:
            logger.error(f"Error retrieving token balances: {e}")
            return []

    def get_full_order_book(self, symbol: str, book_type: str = 'buy', batch_size: int = 100) -> List[dict]:
        """
        Retrieve the full order book (buy or sell) for a token by paging through all orders.

        Args:
            symbol: The token symbol.
            book_type: 'buy' for bids, 'sell' for asks.
            batch_size: Number of orders to fetch per request.

        Returns:
            List of all orders (dicts).
        """
        orders = []
        offset = 0
        while True:
            if book_type == 'buy':
                batch = self.market.get_buy_book(symbol, limit=batch_size, offset=offset)
            else:
                batch = self.market.get_sell_book(symbol, limit=batch_size, offset=offset)
            if not batch:
                break
            orders.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
        return orders

    def get_market_price(self, symbol: str) -> Tuple[float, float]:
        """
        Get the true highest bid and lowest ask prices for a token by draining the full order book.

        Args:
            symbol: The token symbol.

        Returns:
            Tuple of (highest bid price, lowest ask price)
        """
        try:
            # Get all buy orders (bids)
            buy_orders = self.get_full_order_book(symbol, book_type='buy', batch_size=100)
            highest_bid = max((float(order.get('price', 0)) for order in buy_orders), default=0)
            total_bid_quantity = sum(float(order.get('quantity', 0)) for order in buy_orders)
            logger.debug(f"Total buy orders for {symbol}: {total_bid_quantity} at various prices. Highest bid: {highest_bid}")

            # Get all sell orders (asks)
            sell_orders = self.get_full_order_book(symbol, book_type='sell', batch_size=100)
            # Only consider positive prices
            lowest_ask = min((float(order.get('price', float('inf'))) for order in sell_orders if float(order.get('price', 0)) > 0), default=0)
            total_ask_quantity = sum(float(order.get('quantity', 0)) for order in sell_orders)
            logger.debug(f"Total sell orders for {symbol}: {total_ask_quantity} at various prices. Lowest ask: {lowest_ask}")

            logger.debug(f"{symbol} market: highest bid = {highest_bid}, lowest ask = {lowest_ask}")
            return highest_bid, lowest_ask
        except Exception as e:
            logger.error(f"Error getting market price for {symbol}: {e}")
            return 0, 0

    def sell_token(self, symbol: str, amount: float, price: float) -> bool:
        """
        Sell a token on the Hive-Engine market at the best available price (highest bid).

        Args:
            symbol: The token symbol to sell.
            amount: The amount to sell.
            price: The price to sell at (should always be the highest bid, never the lowest ask).

        Returns:
            True if the sell was successful, False otherwise.

        Note:
            You should always sell at the highest bid (best price a buyer is willing to pay).
            Never use the lowest ask as your sell price.
        """
        try:
            # Calculate the total value
            total_value = amount * price

            # Ensure we are not accidentally using the lowest ask as the sell price
            # (This is a sanity check: you want to sell at the highest bid, not the lowest ask)
            if price <= 0:
                logger.error(f"[{self.account_name}] Refusing to sell {symbol} at price <= 0 (invalid highest bid)")
                return False

            # Format for display - this is what will be shown in the log
            formatted_amount = f"{amount:.6f}"
            formatted_price = f"{price:.8f}"
            formatted_total = f"{total_value:.6f}"

            # Log the transaction with the calculated values
            logger.info(
                f"[{self.account_name}] Selling {formatted_amount} {symbol} for {formatted_total} SWAP.HIVE at {formatted_price} SWAP.HIVE/{symbol}. (Best bid)"
            )

            if self.dry_run:
                # No actual transaction in dry run mode
                return True

            # Always sell at the highest bid (best price a buyer is willing to pay)
            self.market.sell(self.account_name, amount, symbol, price)
            logger.info(f"Sell order placed for {amount:.6f} {symbol} at {price:.8f}")

            # Wait for order to process
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Error selling {symbol}: {e}")
            return False

    def buy_token(self, symbol: str, amount: float, price: float) -> bool:
        """
        Buy a token on the Hive-Engine market.

        Args:
            symbol: The token symbol to buy.
            amount: The amount to buy.
            price: The price to buy at.

        Returns:
            True if the buy was successful, False otherwise.
        """
        try:
            # Calculate the total value
            total_value = amount * price

            # Format for display - this is what will be shown in the log
            formatted_amount = f"{amount:.6f}"
            formatted_price = f"{price:.8f}"
            formatted_total = f"{total_value:.6f}"

            # Log the transaction with the calculated values
            logger.info(
                f"[{self.account_name}] Buying {formatted_amount} {symbol} for {formatted_total} SWAP.HIVE at {formatted_price} SWAP.HIVE/{symbol}."
            )

            if self.dry_run:
                # No actual transaction in dry run mode
                return True

            # The Market.buy method signature is: buy(account, amount, symbol, price)
            self.market.buy(self.account_name, amount, symbol, price)
            logger.info(f"Buy order placed for {amount:.6f} {symbol} at {price:.8f}")

            # Wait for order to process
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Error buying {symbol}: {e}")
            return False

    def transfer_token(self, to_account: str, symbol: str, amount: float, memo: str = "Automatic transfer") -> bool:
        """
        Transfer a token to another account.

        Args:
            to_account: The account to transfer to.
            symbol: The token symbol to transfer.
            amount: The amount to transfer.
            memo: The memo to include with the transfer.

        Returns:
            True if the transfer was successful, False otherwise.
        """
        try:
            logger.info(f"Transferring {amount:.6f} {symbol} to {to_account} with memo: {memo}")

            if self.dry_run:
                logger.info(
                    f"[DRY RUN] Would transfer {amount:.6f} {symbol} to {to_account} with memo: {memo}"
                )
                return True

            self.wallet.transfer(to_account, amount, symbol, memo=memo)
            logger.info(f"Transferred {amount:.6f} {symbol} to {to_account}")
            return True
        except Exception as e:
            logger.error(f"Error transferring {symbol}: {e}")
            return False
