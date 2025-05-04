"""
Hive HBD Market Seller
--------------------
This script connects to the Hive blockchain using the nectar library and sells HBD for HIVE on the internal market
for multiple accounts using the authority (active key) of a single main account.

Features:
- Connects to Hive nodes using an active key from the environment, YAML config, or CLI.
- Loops through a list of Hive accounts and sells HBD for each if their balance is above the minimum threshold.
- Uses the authority of the main account (the one whose active key is provided) to sell HBD for all listed accounts.
- Provides informative logging and robust error handling.
- Supports dry-run mode to simulate transactions without broadcasting.
- Allows setting minimum and maximum HBD amounts to sell.

Author: thecrazygm
"""

import argparse
import sys
import traceback
from typing import List

from auto_market.config import get_active_key, load_accounts_and_active_key
from auto_market.hive_client import connect_to_hive
from auto_market.logging_setup import set_debug_logging, setup_logging

# Set up logging
logger = setup_logging()


def sell_hbd_for_all_accounts(
    accounts: List[str],
    main_account_name: str,
    active_key: str,
    min_hbd_amount: float,
    max_hbd: float = None,
    dry_run: bool = False,
) -> None:
    """
    Sell HBD for all accounts in the list using the authority of the main account.

    Args:
        accounts: List of account names to sell HBD for.
        main_account_name: The account whose active key is used for authority.
        active_key: The active key for transaction authority.
        min_hbd_amount: Minimum HBD balance to trigger a sell operation.
        max_hbd: Maximum HBD to sell in one transaction (None = no limit).
        dry_run: If True, only simulate the sell, do not broadcast.
    """
    logger.info(f"Selling HBD for {len(accounts)} accounts using {main_account_name} authority")

    # Connect to Hive blockchain
    try:
        hive = connect_to_hive(active_key, dry_run)
    except Exception as e:
        logger.error(f"Failed to connect to Hive blockchain: {e}")
        return

    # Instantiate the main account for authority
    logger.debug(f"Instantiating main account object for authority: {main_account_name}")
    try:
        from nectar.account import Account
        from nectar.market import Market

        main_account = Account(main_account_name, blockchain_instance=hive)
        market = Market("HIVE:HBD", blockchain_instance=hive)
    except Exception as e:
        logger.error(f"Error loading main account {main_account_name}: {e}")
        return

    logger.debug(f"Account list to process: {accounts}")

    # Process each account in the list
    success_count = 0
    for account_name in accounts:
        try:
            logger.debug(f"Processing account: {account_name}")
            # Instantiate the target account object
            target_account = Account(account_name, blockchain_instance=hive)
            logger.debug(f"[{account_name}] Target account instantiated.")

            # Get the HBD balance
            hbd_balance = target_account.get_balance("available", "HBD")
            logger.debug(f"[{account_name}] HBD balance: {hbd_balance}")

            # Check if there's enough HBD to sell
            if not hbd_balance or hbd_balance.amount <= min_hbd_amount:
                logger.info(f"[{account_name}] No HBD to sell (minimum: {min_hbd_amount}).")
                continue

            # Calculate how much HBD to sell
            available_hbd = float(hbd_balance.amount)
            if max_hbd is not None and available_hbd > max_hbd:
                logger.info(
                    f"[{account_name}] Limiting HBD to sell from {available_hbd:.3f} to max_hbd={max_hbd:.3f}"
                )
                available_hbd = max_hbd

            # Get market data and calculate HIVE to buy
            ticker = market.ticker()
            low_ask = float(ticker["lowest_ask"]["price"])
            buy_amount = available_hbd / low_ask
            logger.info(
                f"[{account_name}] Selling {available_hbd:.3f} HBD for {buy_amount:.3f} HIVE at {low_ask:.3f} HBD/HIVE."
            )

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would sell {available_hbd:.3f} HBD for {account_name} using authority of {main_account_name}."
                )
                logger.debug(
                    f"[DRY RUN] market.buy({low_ask}, {buy_amount}, account={account_name}) would be called here."
                )
                success_count += 1
            else:
                logger.debug(
                    f"Calling main_account.market.buy({low_ask}, {buy_amount}, account={account_name})..."
                )
                # Use the main account's authority to execute the market buy
                main_account.market.buy(low_ask, buy_amount, account=account_name)
                logger.info(
                    f"[{account_name}] HBD sold successfully using authority of {main_account_name}."
                )
                success_count += 1

        except Exception as e:
            logger.error(f"Error processing account {account_name}: {type(e).__name__}: {e}")
            logger.debug(traceback.format_exc())
            # Try to print account JSON for debugging if possible
            try:
                logger.debug(
                    f"{account_name} account json: {getattr(target_account, 'json', None)}"
                )
            except Exception:
                logger.debug(f"Could not retrieve account JSON for {account_name}")

    logger.info(f"Successfully processed {success_count} out of {len(accounts)} accounts")


def main() -> None:
    """
    Main entry point for the Hive HBD Market Seller script.
    Parses command-line arguments, loads the active key, connects to Hive,
    and sells HBD for all accounts in the configuration.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Sell HBD for multiple Hive accounts using a single active key"
    )
    parser.add_argument(
        "-a",
        "--accounts",
        help="Path to YAML file containing accounts list and optional active key",
    )
    parser.add_argument(
        "-k",
        "--active-key",
        help="Active key for transaction authority (overrides YAML and environment)",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate selling HBD without broadcasting",
    )
    parser.add_argument(
        "-m",
        "--min-hbd-amount",
        type=float,
        default=0.001,
        help="Minimum HBD amount to trigger a sell (default: 0.001 HBD)",
    )
    parser.add_argument(
        "-x",
        "--max-hbd",
        type=float,
        default=None,
        help="Maximum HBD to sell in one run (default: no limit)",
    )
    args = parser.parse_args()

    # Set logging level if debug flag is used
    if args.debug:
        set_debug_logging(logger)

    # Load accounts list, active key, and whitelist from YAML file or fallback
    accounts, yaml_active_key, whitelist = load_accounts_and_active_key(args.accounts)

    # Ensure we have at least one account
    if not accounts:
        logger.error("No accounts found in configuration")
        sys.exit(1)

    # Retrieve the active key from CLI, YAML, or environment
    active_key = get_active_key(args.active_key, yaml_active_key)

    # Use the first account in the list as the authority
    authority_account = accounts[0]
    logger.debug(f"Using authority account: {authority_account}")

    # Set operational parameters
    dry_run = args.dry_run
    min_hbd_amount = args.min_hbd_amount
    max_hbd = args.max_hbd

    # Sell HBD for all listed accounts
    sell_hbd_for_all_accounts(
        accounts, authority_account, active_key, min_hbd_amount, max_hbd, dry_run=dry_run
    )


if __name__ == "__main__":
    # Script entry point. Handles any uncaught exceptions gracefully.
    try:
        main()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
