"""
Hive blockchain connectivity module.
Provides functions for connecting to the Hive blockchain and performing common operations.
"""

import logging
from typing import Optional

from nectar import Hive
from nectar.account import Account
from nectar.market import Market
from nectar.nodelist import NodeList
from nectar.wallet import Wallet

logger = logging.getLogger(__name__)


def connect_to_hive(active_key: str, dry_run: bool = False) -> Hive:
    """
    Establish a connection to the Hive blockchain using the provided active key.
    Automatically selects the best available Hive nodes.

    Args:
        active_key: The active private key.
        dry_run: If True, transactions will not be broadcast.

    Returns:
        A connected Hive blockchain instance.

    Raises:
        Exception: If connection fails.
    """
    try:
        logger.debug("Initializing NodeList and updating nodes...")
        nodelist = NodeList()
        nodelist.update_nodes()
        nodes = nodelist.get_hive_nodes()

        logger.info(f"Connecting to Hive nodes: {nodes}")
        hive = Hive(keys=[active_key], node=nodes, nobroadcast=dry_run)
        logger.info("Connected to Hive blockchain.")
        return hive
    except Exception as e:
        logger.error(f"Failed to connect to Hive: {e}")
        raise


class HiveTrader:
    """
    Class for handling Hive market trading operations.
    """

    def __init__(self, hive: Hive, min_hbd_amount: float, max_hbd: Optional[float] = None):
        """
        Initialize Hive trading instance.

        Args:
            hive: Connected Hive blockchain instance
            min_hbd_amount: Minimum HBD balance to trigger a sell operation
            max_hbd: Maximum HBD to sell in one transaction (None = no limit)
        """
        logger.debug(
            f"Initializing HiveTrader with min_hbd_amount={min_hbd_amount}, max_hbd={max_hbd}"
        )
        self.hive = hive
        self.min_hbd_amount = min_hbd_amount
        self.max_hbd = max_hbd
        self.wallet = Wallet(blockchain_instance=self.hive)
        self.market = Market("HIVE:HBD", blockchain_instance=self.hive)
        logger.debug("HiveTrader initialized successfully")

    def sell_hbd(self, account_name: str) -> bool:
        """
        Sell HBD for HIVE at the market's lowest ask price.
        Uses the authority of the key provided during HiveTrader initialization.

        Args:
            account_name: Account whose HBD balance is checked and sold.

        Returns:
            True if rewards were claimed or there were none to claim, False on error.
        """
        try:
            logger.debug(f"Instantiating account object for: {account_name}")
            account = Account(account_name, blockchain_instance=self.hive)
            hbd_balance = account.get_balance("available", "HBD")
            logger.info(
                f"[{account_name}] HBD to sell: {hbd_balance if hbd_balance else '0.000 HBD'}"
            )

            # Check if there's enough HBD to sell
            if not hbd_balance or hbd_balance.amount <= self.min_hbd_amount:
                logger.info(f"[{account_name}] No HBD to sell.")
                return True  # Not an error, just nothing to do

            # Calculate how much HBD to sell
            available_hbd = float(hbd_balance.amount)
            if self.max_hbd is not None and available_hbd > self.max_hbd:
                logger.info(
                    f"[{account_name}] Limiting HBD to sell from {available_hbd:.3f} to max_hbd={self.max_hbd:.3f}"
                )
                available_hbd = self.max_hbd

            # Get market data and calculate HIVE to buy
            ticker = self.market.ticker()
            low_ask = float(ticker["lowest_ask"]["price"])
            buy_amount = available_hbd / low_ask
            logger.info(
                f"[{account_name}] Selling {available_hbd:.3f} HBD for {buy_amount:.3f} HIVE at {low_ask:.3f} HBD/HIVE."
            )

            # Execute the market buy (selling HBD for HIVE)
            tx = self.market.buy(low_ask, buy_amount, account=account_name)

            if self.hive.nobroadcast:
                logger.info(
                    f"[{account_name}] [DRY RUN] Would have bought {buy_amount:.3f} HIVE with {available_hbd:.3f} HBD."
                )
                logger.debug(f"[DRY RUN] Transaction details: {tx}")
            else:
                logger.info(f"[{account_name}] Market buy order placed successfully.")
                logger.debug(f"Transaction details: {tx}")
            return True

        except Exception as e:
            import traceback

            logger.error(f"Error selling HBD for {account_name}: {type(e).__name__}: {e}")
            logger.debug(traceback.format_exc())
            return False
