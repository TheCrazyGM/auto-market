"""
Hive HBD Market Trader
--------------------
This script connects to the Hive blockchain using the nectar library and trades HBD for HIVE (or vice versa)
on the internal market for multiple accounts using the authority (active key) of a single main account.

Features:
- Connects to Hive nodes using an active key from the environment, YAML config, or CLI.
- Loops through a list of Hive accounts and trades HBD/HIVE if their balance is above the minimum threshold.
- Supports both selling HBD for HIVE and buying HBD with HIVE.
- Uses the authority of the main account (the one whose active key is provided) for all listed accounts.
- Provides informative logging and robust error handling.
- Supports dry-run mode to simulate transactions without broadcasting.
- Allows setting minimum and maximum amounts to trade.

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


def buy_hbd_for_all_accounts(
    accounts: List[str],
    main_account_name: str,
    active_key: str,
    min_hive_amount: float,
    max_hive: float = None,
    dry_run: bool = False,
) -> None:
    """
    Buy HBD for all accounts in the list using the authority of the main account.

    Args:
        accounts: List of account names to buy HBD for.
        main_account_name: The account whose active key is used for authority.
        active_key: The active key for transaction authority.
        min_hive_amount: Minimum HIVE balance to trigger a buy operation.
        max_hive: Maximum HIVE to use in one transaction (None = no limit).
        dry_run: If True, only simulate the buy, do not broadcast.
    """
    logger.info(f"Buying HBD for {len(accounts)} accounts using {main_account_name} authority")

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

            # Get the HIVE balance
            hive_balance = target_account.get_balance("available", "HIVE")
            logger.debug(f"[{account_name}] HIVE balance: {hive_balance}")

            # Check if there's enough HIVE to buy HBD
            if not hive_balance or hive_balance.amount <= min_hive_amount:
                logger.info(
                    f"[{account_name}] Not enough HIVE to buy HBD (minimum: {min_hive_amount})."
                )
                continue

            # Calculate how much HIVE to use
            available_hive = float(hive_balance.amount)
            if max_hive is not None and available_hive > max_hive:
                logger.info(
                    f"[{account_name}] Limiting HIVE to use from {available_hive:.3f} to max_hive={max_hive:.3f}"
                )
                available_hive = max_hive

            # Get market data and calculate HBD to buy
            ticker = market.ticker()
            high_bid = float(ticker["highest_bid"]["price"])
            buy_hbd_amount = available_hive * high_bid
            logger.info(
                f"[{account_name}] Buying {buy_hbd_amount:.3f} HBD with {available_hive:.3f} HIVE at {high_bid:.3f} HBD/HIVE."
            )

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would buy {buy_hbd_amount:.3f} HBD for {account_name} using authority of {main_account_name}."
                )
                logger.debug(
                    f"[DRY RUN] market.sell({high_bid}, {available_hive}, account={account_name}) would be called here."
                )
                success_count += 1
            else:
                logger.debug(
                    f"Calling main_account.market.sell({high_bid}, {available_hive}, account={account_name})..."
                )
                # Use the main account's authority to execute the market sell
                main_account.market.sell(high_bid, available_hive, account=account_name)
                logger.info(
                    f"[{account_name}] HBD bought successfully using authority of {main_account_name}."
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
    Main entry point for the Hive HBD Market Trader script.
    Parses command-line arguments, loads the active key, connects to Hive,
    and trades HBD/HIVE for all accounts in the configuration based on the operation mode.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Trade HBD/HIVE for multiple Hive accounts using a single active key"
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
        help="Simulate trading without broadcasting",
    )
    parser.add_argument(
        "-o",
        "--operation",
        choices=["sell", "buy"],
        default="sell",
        help="Operation mode: 'sell' HBD for HIVE or 'buy' HBD with HIVE (default: sell)",
    )
    parser.add_argument(
        "-m",
        "--min-amount",
        type=float,
        default=0.001,
        help="Minimum amount to trigger a trade operation (default: 0.001)",
    )
    parser.add_argument(
        "-x",
        "--max-amount",
        type=float,
        default=None,
        help="Maximum amount to trade in one run (default: no limit)",
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
    operation = args.operation
    min_amount = args.min_amount
    max_amount = args.max_amount

    # Execute the requested operation
    if operation == "sell":
        logger.info("Operation mode: Selling HBD for HIVE")
        sell_hbd_for_all_accounts(
            accounts, authority_account, active_key, min_amount, max_amount, dry_run=dry_run
        )
    else:  # operation == "buy"
        logger.info("Operation mode: Buying HBD with HIVE")
        buy_hbd_for_all_accounts(
            accounts, authority_account, active_key, min_amount, max_amount, dry_run=dry_run
        )


if __name__ == "__main__":
    # Script entry point. Handles any uncaught exceptions gracefully.
    try:
        main()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
