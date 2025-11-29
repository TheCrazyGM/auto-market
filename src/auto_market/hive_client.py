"""
Hive blockchain connectivity module.
Provides functions for connecting to the Hive blockchain and performing common operations.
"""

import logging
from typing import Optional

from nectar import Hive
from nectar.account import Account
from nectar.market import Market
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
        logger.info("Connecting to Hive blockchain...")
        # Let Hive handle node initialization internally to avoid duplicate beacon calls
        hive = Hive(keys=[active_key], nobroadcast=dry_run)
        logger.info("Connected to Hive blockchain.")
        return hive
    except Exception as e:
        logger.error(f"Failed to connect to Hive: {e}")
        raise


class HiveTrader:
    """
    Class for handling Hive market trading operations.
    Supports both selling HBD for HIVE and buying HBD with HIVE.
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
            True if operation was successful, False on error.
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
                f"[{account_name}] Selling {available_hbd:.6f} HBD for {buy_amount:.6f} HIVE at {low_ask:.8f} HBD/HIVE."
            )

            # Format values for consistent display
            formatted_hbd = f"{available_hbd:.6f}"
            formatted_hive = f"{buy_amount:.6f}"
            formatted_price = f"{low_ask:.8f}"

            # Execute the market buy (selling HBD for HIVE)
            tx = self.market.buy(low_ask, buy_amount, account=account_name)

            if self.hive.nobroadcast:
                logger.info(
                    f"[{account_name}] [DRY RUN] Would have bought {formatted_hive} HIVE with {formatted_hbd} HBD at {formatted_price} HBD/HIVE."
                )
                logger.debug(f"[DRY RUN] Transaction details: {tx}")
            else:
                logger.info(
                    f"[{account_name}] Market buy order placed successfully for {formatted_hive} HIVE with {formatted_hbd} HBD."
                )
                logger.debug(f"Transaction details: {tx}")
            return True

        except Exception as e:
            import traceback

            logger.error(f"Error selling HBD for {account_name}: {type(e).__name__}: {e}")
            logger.debug(traceback.format_exc())
            return False

    def buy_hbd(
        self, account_name: str, min_hive_amount: float, max_hive: Optional[float] = None
    ) -> bool:
        """
        Buy HBD with HIVE at the market's highest bid price.
        Uses the authority of the key provided during HiveTrader initialization.

        Args:
            account_name: Account whose HIVE balance is checked and used to buy HBD.
            min_hive_amount: Minimum HIVE balance to trigger a buy operation.
            max_hive: Maximum HIVE to use in one transaction (None = no limit).

        Returns:
            True if operation was successful, False on error.
        """
        try:
            logger.debug(f"Instantiating account object for: {account_name}")
            account = Account(account_name, blockchain_instance=self.hive)
            hive_balance = account.get_balance("available", "HIVE")
            logger.info(
                f"[{account_name}] HIVE available to buy HBD: {hive_balance if hive_balance else '0.000 HIVE'}"
            )

            # Check if there's enough HIVE to buy HBD
            if not hive_balance or hive_balance.amount <= min_hive_amount:
                logger.info(
                    f"[{account_name}] Not enough HIVE to buy HBD (minimum: {min_hive_amount})."
                )
                return True  # Not an error, just nothing to do

            # Calculate how much HIVE to use
            available_hive = float(hive_balance.amount)
            if max_hive is not None and available_hive > max_hive:
                logger.info(
                    f"[{account_name}] Limiting HIVE to use from {available_hive:.3f} to max_hive={max_hive:.3f}"
                )
                available_hive = max_hive

            # Get market data and calculate HBD to buy
            ticker = self.market.ticker()
            high_bid = float(ticker["highest_bid"]["price"])
            sell_amount = available_hive
            buy_hbd_amount = available_hive * high_bid
            logger.info(
                f"[{account_name}] Buying {buy_hbd_amount:.6f} HBD with {sell_amount:.6f} HIVE at {high_bid:.8f} HBD/HIVE."
            )

            # Format values for consistent display
            formatted_hbd = f"{buy_hbd_amount:.6f}"
            formatted_hive = f"{sell_amount:.6f}"
            formatted_price = f"{high_bid:.8f}"

            # Execute the market sell (selling HIVE for HBD)
            tx = self.market.sell(high_bid, sell_amount, account=account_name)

            if self.hive.nobroadcast:
                logger.info(
                    f"[{account_name}] [DRY RUN] Would have bought {formatted_hbd} HBD with {formatted_hive} HIVE at {formatted_price} HBD/HIVE."
                )
                logger.debug(f"[DRY RUN] Transaction details: {tx}")
            else:
                logger.info(
                    f"[{account_name}] Market sell order placed successfully for {formatted_hbd} HBD with {formatted_hive} HIVE."
                )
                logger.debug(f"Transaction details: {tx}")
            return True

        except Exception as e:
            import traceback

            logger.error(f"Error buying HBD for {account_name}: {type(e).__name__}: {e}")
            logger.debug(traceback.format_exc())
            return False


def stake_hbd(
    hive: Hive,
    account_name: str,
    min_hbd_amount: float = 0.001,
    max_hbd_amount: Optional[float] = None,
    memo: str = "auto to savings",
) -> bool:
    """
    Transfer available HBD to savings for a specific account.

    Args:
        hive: Connected Hive instance (respects hive.nobroadcast for dry-run).
        account_name: The Hive account to operate on.
        min_hbd_amount: Minimum HBD to trigger a transfer.
        max_hbd_amount: Optional cap for transfer amount.
        memo: Memo to include with the transfer.

    Returns:
        True if operation succeeded or was a no-op due to thresholds; False on error.
    """
    try:
        account = Account(account_name, blockchain_instance=hive)
        hbd_balance = account.get_balance("available", "HBD")
        logger.info(
            f"[{account_name}] HBD available to stake: {hbd_balance if hbd_balance else '0.000 HBD'}"
        )

        if not hbd_balance or hbd_balance.amount <= min_hbd_amount:
            logger.info(f"[{account_name}] Available HBD below threshold. Skipping.")
            return True

        amount = float(hbd_balance.amount)
        if max_hbd_amount is not None and amount > max_hbd_amount:
            logger.info(
                f"[{account_name}] Limiting HBD to stake from {amount:.3f} to max_hbd_amount={max_hbd_amount:.3f}"
            )
            amount = max_hbd_amount

        # Execute or simulate
        if hive.nobroadcast:
            logger.info(
                f"[{account_name}] [DRY RUN] Would transfer {amount:.3f} HBD to savings with memo '{memo}'."
            )
            return True

        tx = account.transfer_to_savings(amount, "HBD", memo=memo, account=account_name)
        logger.info(f"[{account_name}] transfer_to_savings broadcasted: {tx.get('trx_id', 'N/A')}")
        logger.debug(f"Transaction details: {tx}")
        return True
    except Exception as e:
        import traceback

        logger.error(f"Error staking HBD for {account_name}: {type(e).__name__}: {e}")
        logger.debug(traceback.format_exc())
        return False


def powerup_hive(
    hive: Hive,
    account_name: str,
    min_hive_amount: float = 0.001,
    max_hive_amount: Optional[float] = None,
) -> bool:
    """
    Power up available HIVE (transfer to vesting) for a specific account.

    Args:
        hive: Connected Hive instance (respects hive.nobroadcast for dry-run).
        account_name: The Hive account to operate on.
        min_hive_amount: Minimum HIVE to trigger a power up.
        max_hive_amount: Optional cap for power up amount.

    Returns:
        True if operation succeeded or was a no-op due to thresholds; False on error.
    """
    try:
        account = Account(account_name, blockchain_instance=hive)
        hive_balance = account.get_balance("available", "HIVE")
        logger.info(
            f"[{account_name}] HIVE available to power up: {hive_balance if hive_balance else '0.000 HIVE'}"
        )

        if not hive_balance or hive_balance.amount <= min_hive_amount:
            logger.info(f"[{account_name}] Available HIVE below threshold. Skipping.")
            return True

        amount = float(hive_balance.amount)
        if max_hive_amount is not None and amount > max_hive_amount:
            logger.info(
                f"[{account_name}] Limiting HIVE to power up from {amount:.3f} to max_hive_amount={max_hive_amount:.3f}"
            )
            amount = max_hive_amount

        if hive.nobroadcast:
            logger.info(f"[{account_name}] [DRY RUN] Would power up {amount:.3f} HIVE to vesting.")
            return True

        tx = account.transfer_to_vesting(amount, account=account_name)
        logger.info(f"[{account_name}] transfer_to_vesting broadcasted: {tx.get('trx_id', 'N/A')}")
        logger.debug(f"Transaction details: {tx}")
        return True
    except Exception as e:
        import traceback

        logger.error(f"Error powering up HIVE for {account_name}: {type(e).__name__}: {e}")
        logger.debug(traceback.format_exc())
        return False
