"""
Hive-Engine Token Market Seller
----------------------------
This script connects to the Hive blockchain and Hive-Engine sidechain to sell tokens
for multiple accounts using the authority (active key) of a single main account.

Features:
- Connects to Hive nodes using an active key from the environment, YAML config, or CLI.
- Fetches token balances from Hive-Engine for each account.
- Sells specified tokens at the current market price.
- Uses the authority of the main account (the one whose active key is provided).
- Provides informative logging and robust error handling.
- Supports dry-run mode to simulate sells without broadcasting.

Author: thecrazygm
"""

import argparse
import sys
import time
import traceback
from typing import List, Optional

from auto_market.config import get_active_key, load_accounts_and_active_key
from auto_market.he_client import (
    connect_to_hive_engine,
    get_market_price,
    get_token_balances,
    sell_token,
)
from auto_market.hive_client import connect_to_hive
from auto_market.logging_setup import set_debug_logging, setup_logging

# Set up logging
logger = setup_logging()


def sell_he_tokens_for_all_accounts(
    accounts: List[str],
    main_account_name: str,
    active_key: str,
    token_symbol: str,
    min_token_amount: float,
    max_token_amount: Optional[float] = None,
    target_token: str = "SWAP.HIVE",
    sell_all: bool = False,
    whitelist: List[str] = None,
    dry_run: bool = False,
) -> None:
    """
    Sell Hive-Engine tokens for all accounts in the list using the authority of the main account.

    Args:
        accounts: List of account names to sell tokens for.
        main_account_name: The account whose active key is used for authority.
        active_key: The active key for transaction authority.
        token_symbol: The token symbol to sell (ignored if sell_all is True).
        min_token_amount: Minimum token balance to trigger a sell operation.
        max_token_amount: Maximum token amount to sell in one transaction (None = no limit).
        target_token: The token to sell for (default: SWAP.HIVE).
        sell_all: If True, sell all tokens except those in the whitelist.
        whitelist: List of token symbols to exclude when sell_all is True.
        dry_run: If True, only simulate the sell, do not broadcast.
    """
    if sell_all:
        logger.info(
            f"Selling ALL non-whitelisted tokens for {len(accounts)} accounts using {main_account_name} authority"
        )
        if whitelist:
            logger.debug(f"Whitelist: {whitelist}")
        else:
            logger.warning("No whitelist specified. All tokens may be sold.")
    else:
        logger.info(
            f"Selling {token_symbol} tokens for {len(accounts)} accounts using {main_account_name} authority"
        )

    # Connect to Hive blockchain
    try:
        hive = connect_to_hive(active_key, dry_run)
    except Exception as e:
        logger.error(f"Failed to connect to Hive blockchain: {e}")
        return

    # Initialize Hive-Engine market
    try:
        # We only need the market from the main account
        _, market = connect_to_hive_engine(hive, main_account_name)
    except Exception as e:
        logger.error(f"Failed to initialize Hive-Engine: {e}")
        return

    logger.debug(f"Account list to process: {accounts}")

    # Process each account in the list
    success_count = 0  # Count of successful token sales
    processed_accounts = 0  # Count of successfully processed accounts
    for account_name in accounts:
        try:
            logger.debug(f"Processing account: {account_name}")
            account_success = False  # Track if this account had any successful sales

            # Create a wallet specific to this account
            try:
                account_wallet, _ = connect_to_hive_engine(hive, account_name)
                logger.debug(f"[{account_name}] Hive-Engine wallet initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Hive-Engine wallet for {account_name}: {e}")
                continue

            # Get token balances for the account
            tokens = get_token_balances(account_wallet)
            logger.debug(f"[{account_name}] Retrieved {len(tokens)} token balances")

            # Process tokens based on mode
            tokens_to_process = []

            if sell_all:
                # Filter tokens to sell (exclude target token and whitelisted tokens)
                tokens_to_process = [
                    t
                    for t in tokens
                    if t.symbol != target_token
                    and t.symbol not in (whitelist or [])
                    and t.balance > min_token_amount
                ]
                logger.debug(f"[{account_name}] Found {len(tokens_to_process)} tokens to sell")
            else:
                # Find the specified token
                token = next((t for t in tokens if t.symbol == token_symbol), None)
                if not token:
                    logger.info(f"[{account_name}] No {token_symbol} tokens found.")
                    continue

                logger.debug(f"[{account_name}] {token_symbol} balance: {token.balance}")

                # Check if there's enough of the token to sell
                if token.balance <= min_token_amount:
                    logger.info(
                        f"[{account_name}] Not enough {token_symbol} to sell (minimum: {min_token_amount})."
                    )
                    continue

                tokens_to_process = [token]

            # Process each token that needs to be sold
            for token in tokens_to_process:
                # Calculate how much of the token to sell
                sell_amount = token.balance
                if max_token_amount is not None and sell_amount > max_token_amount:
                    logger.info(
                        f"[{account_name}] Limiting {token.symbol} to sell from {sell_amount:.6f} to max_amount={max_token_amount:.6f}"
                    )
                    sell_amount = max_token_amount

                # Get market data
                highest_bid, _ = get_market_price(market, token.symbol)
                if highest_bid <= 0:
                    logger.warning(f"[{account_name}] No buyers for {token.symbol}, skipping.")
                    continue

                logger.info(
                    f"[{account_name}] Selling {sell_amount:.6f} {token.symbol} at {highest_bid:.6f} {target_token}"
                )

                # Execute the sell
                if sell_token(
                    market,
                    account_name,
                    token.symbol,
                    sell_amount,
                    highest_bid,
                    dry_run,
                ):
                    if dry_run:
                        logger.info(
                            f"[DRY RUN] Would sell {sell_amount:.6f} {token.symbol} at {highest_bid:.8f} {target_token} for {account_name} using authority of {main_account_name}."
                        )
                    else:
                        logger.info(
                            f"[{account_name}] {token.symbol} sold successfully at {highest_bid:.8f} {target_token} using authority of {main_account_name}."
                        )
                    # Count each successful token sale
                    success_count += 1
                    account_success = True
                else:
                    logger.error(f"[{account_name}] Failed to sell {token.symbol}.")
                    continue

            # If we had any successful sales for this account, increment the account counter
            if account_success:
                processed_accounts += 1

        except Exception as e:
            logger.error(f"Error processing account {account_name}: {type(e).__name__}: {e}")
            logger.debug(traceback.format_exc())

    # Report both token sales and account statistics
    logger.info(
        f"Successfully sold {success_count} tokens from {processed_accounts} out of {len(accounts)} accounts"
    )


def main() -> None:
    """
    Main entry point for the Hive-Engine Token Market Seller script.
    Parses command-line arguments, loads the active key, connects to Hive-Engine,
    and sells tokens for all accounts in the configuration.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Sell Hive-Engine tokens for multiple Hive accounts using a single active key"
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
        "-t",
        "--token",
        help="Token symbol to sell (e.g., SWAP.BTC, LEO, etc.). Not required if --all-tokens is used.",
    )
    parser.add_argument(
        "-A",
        "--all-tokens",
        action="store_true",
        help="Sell all tokens except those in the whitelist",
    )
    parser.add_argument(
        "-m",
        "--min-amount",
        type=float,
        default=0.00001,
        help="Minimum token amount to trigger a sell (default: 0.00001)",
    )
    parser.add_argument(
        "-x",
        "--max-amount",
        type=float,
        default=None,
        help="Maximum token amount to sell in one run (default: no limit)",
    )
    parser.add_argument(
        "--target",
        default="SWAP.HIVE",
        help="Target token to sell for (default: SWAP.HIVE)",
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
        help="Simulate selling tokens without broadcasting",
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
    main_account_name = accounts[0]
    logger.debug(f"Using authority account: {main_account_name}")

    # Validate arguments
    if not args.all_tokens and not args.token:
        logger.error("Either --token or --all-tokens must be specified")
        sys.exit(1)

    if args.all_tokens:
        logger.info(f"Using whitelist from config: {whitelist}")
        token_symbol = ""  # Not used in sell-all mode
    else:
        token_symbol = args.token

    # Sell tokens for all listed accounts
    sell_he_tokens_for_all_accounts(
        accounts,
        main_account_name,
        active_key,
        token_symbol,
        args.min_amount,
        args.max_amount,
        args.target,
        sell_all=args.all_tokens,
        whitelist=whitelist,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    # Script entry point. Handles any uncaught exceptions gracefully.
    try:
        main()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
