"""
Hive blockchain connectivity module.
Provides functions for connecting to the Hive blockchain and performing common operations.
"""

import logging
from typing import Optional

from nectar import Hive
from nectar.account import Account

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
