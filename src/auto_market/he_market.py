"""
Hive-Engine Token Market Trader
----------------------------
This script connects to the Hive blockchain and Hive-Engine sidechain to trade tokens
for multiple accounts using the authority (active key) of a single main account.

Features:
- Connects to Hive nodes using an active key from the environment, YAML config, or CLI.
- Fetches token balances from Hive-Engine for each account.
- Sells or buys specified tokens at the current market price.
- Uses the authority of the main account (the one whose active key is provided).
- Provides colorful Rich-based logging and robust error handling.
- Supports dry-run mode to simulate trades without broadcasting.

Author: thecrazygm
"""

import argparse
import sys
import traceback
from typing import List, Optional

from auto_market.config import get_active_key, load_accounts_and_active_key
from auto_market.he_client import HiveEngineTrader
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

    # We don't need to initialize a trader for the main account here
    # Each account will have its own trader instance

    logger.debug(f"Account list to process: {accounts}")

    # Process each account in the list
    success_count = 0  # Count of successful token sales
    processed_accounts = 0  # Count of successfully processed accounts
    for account_name in accounts:
        try:
            logger.debug(f"Processing account: {account_name}")
            account_success = False  # Track if this account had any successful sales

            # Create a trader specific to this account
            try:
                account_trader = HiveEngineTrader(
                    hive, account_name, min_token_amount, max_token_amount
                )
                logger.debug(f"[{account_name}] Hive-Engine trader initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Hive-Engine trader for {account_name}: {e}")
                continue

            # Get token balances for the account
            tokens = account_trader.get_token_balances()
            logger.debug(f"[{account_name}] Retrieved {len(tokens)} token balances")

            # Process tokens based on mode
            tokens_to_process = []

            if sell_all:
                # Filter tokens to sell (exclude target token and whitelisted tokens)
                tokens_to_process = [
                    t
                    for t in tokens
                    if t.symbol.upper() != target_token.upper()
                    and t.symbol.upper() not in (whitelist or [])
                    and t.balance > min_token_amount
                ]
                logger.debug(f"[{account_name}] Found {len(tokens_to_process)} tokens to sell")
            else:
                # Find the specified token (case-insensitive matching)
                token = next((t for t in tokens if t.symbol.upper() == token_symbol.upper()), None)
                if not token:
                    logger.info(f"[{account_name}] No {token_symbol} tokens found.")
                    continue

                logger.debug(f"[{account_name}] {token_symbol} balance: {token.balance}")

                # Check if there's enough of the token to sell
                if token.balance <= min_token_amount:
                    logger.info(
                        f"[{account_name}] Not enough {token_symbol} to sell (minimum: {min_token_amount:.6f})."
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
                highest_bid, _ = account_trader.get_market_price(token.symbol)
                if highest_bid <= 0:
                    logger.warning(f"[{account_name}] No buyers for {token.symbol}, skipping.")
                    continue

                logger.info(
                    f"[{account_name}] Selling {sell_amount:.6f} {token.symbol} at {highest_bid:.6f} {target_token}"
                )

                # Format values for consistent display
                formatted_amount = f"{sell_amount:.6f}"
                formatted_price = f"{highest_bid:.8f}"

                # Execute the sell
                if account_trader.sell_token(
                    token.symbol,
                    sell_amount,
                    highest_bid,
                ):
                    if dry_run:
                        logger.info(
                            f"[DRY RUN] Would sell {formatted_amount} {token.symbol} at {formatted_price} {target_token} for {account_name} using authority of {main_account_name}."
                        )
                    else:
                        logger.info(
                            f"[{account_name}] {token.symbol} sold successfully at {formatted_price} {target_token} using authority of {main_account_name}."
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


def stake_he_tokens_for_all_accounts(
    accounts: List[str],
    main_account_name: str,
    active_key: str,
    token_symbol: str,
    min_token_amount: float,
    max_token_amount: Optional[float] = None,
    target_token: str = "SWAP.HIVE",
    stake_all: bool = False,
    whitelist: Optional[List[str]] = None,
    dry_run: bool = False,
) -> None:
    """Stake Hive-Engine tokens for all accounts.

    Args:
        accounts: list of account names.
        main_account_name: authority account.
        active_key: active key.
        token_symbol: token to stake when stake_all is False.
        min_token_amount: minimum amount to trigger staking.
        max_token_amount: maximum amount per transaction.
        target_token: unused, kept for signature consistency.
        stake_all: if True stake all stakeable tokens except whitelist.
        whitelist: tokens to skip when staking all.
        dry_run: simulate only.
    """
    if stake_all:
        logger.info(
            f"Staking ALL stakeable non-whitelisted tokens for {len(accounts)} accounts using {main_account_name} authority"
        )
        if whitelist:
            logger.debug(f"Whitelist: {whitelist}")
    else:
        logger.info(
            f"Staking {token_symbol} tokens for {len(accounts)} accounts using {main_account_name} authority"
        )

    # Connect to Hive
    try:
        hive = connect_to_hive(active_key, dry_run)
    except Exception as e:
        logger.error(f"Failed to connect to Hive blockchain: {e}")
        return

    success_count = 0
    processed_accounts = 0
    for account_name in accounts:
        try:
            account_trader = HiveEngineTrader(
                hive, account_name, min_token_amount, max_token_amount
            )
            tokens = account_trader.get_token_balances()
            logger.debug(f"[{account_name}] Retrieved {len(tokens)} token balances")

            # Filter tokens to process
            if stake_all:
                candidate_tokens = [
                    t for t in tokens if t.symbol.upper() not in (whitelist or [])
                ]
            else:
                candidate_tokens = [
                    t for t in tokens if t.symbol.upper() == token_symbol.upper()
                ]

            for tok in candidate_tokens:
                amount = tok.balance
                if account_trader.stake_token(tok.symbol, amount):
                    success_count += 1
                    processed_accounts += 1
        except Exception as e:
            logger.error(f"Error processing account {account_name}: {type(e).__name__}: {e}")
            logger.debug(traceback.format_exc())

    logger.info(
        f"Successfully staked {success_count} token balances across {processed_accounts} accounts"
    )


# ---------------- Existing buy function below ----------------

def buy_he_tokens_for_all_accounts(
    accounts: List[str],
    main_account_name: str,
    active_key: str,
    token_symbol: str,
    min_swap_hive_amount: float,
    max_swap_hive_amount: Optional[float] = None,
    target_token: str = "SWAP.HIVE",
    dry_run: bool = False,
) -> None:
    """
    Buy Hive-Engine tokens for all accounts in the list using the authority of the main account.

    Args:
        accounts: List of account names to buy tokens for.
        main_account_name: The account whose active key is used for authority.
        active_key: The active key for transaction authority.
        token_symbol: The token symbol to buy.
        min_swap_hive_amount: Minimum SWAP.HIVE balance to trigger a buy operation.
        max_swap_hive_amount: Maximum SWAP.HIVE amount to use in one transaction (None = no limit).
        target_token: The token to use for buying (default: SWAP.HIVE).
        dry_run: If True, only simulate the buy, do not broadcast.
    """
    logger.info(
        f"Buying {token_symbol} tokens for {len(accounts)} accounts using {main_account_name} authority"
    )

    # Connect to Hive blockchain
    try:
        hive = connect_to_hive(active_key, dry_run)
    except Exception as e:
        logger.error(f"Failed to connect to Hive blockchain: {e}")
        return

    # We don't need to initialize a trader for the main account here
    # Each account will have its own trader instance

    logger.debug(f"Account list to process: {accounts}")

    # Process each account in the list
    success_count = 0  # Count of successful token buys
    processed_accounts = 0  # Count of successfully processed accounts
    for account_name in accounts:
        try:
            logger.debug(f"Processing account: {account_name}")
            account_success = False  # Track if this account had any successful buys

            # Create a trader specific to this account
            try:
                account_trader = HiveEngineTrader(
                    hive, account_name, min_swap_hive_amount, max_swap_hive_amount
                )
                logger.debug(f"[{account_name}] Hive-Engine trader initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Hive-Engine trader for {account_name}: {e}")
                continue

            # Get token balances for the account
            tokens = account_trader.get_token_balances()
            logger.debug(f"[{account_name}] Retrieved {len(tokens)} token balances")

            # Find the target token (SWAP.HIVE) balance
            swap_hive_token = next(
                (t for t in tokens if t.symbol.upper() == target_token.upper()), None
            )
            if not swap_hive_token:
                logger.info(f"[{account_name}] No {target_token} tokens found.")
                continue

            logger.debug(f"[{account_name}] {target_token} balance: {swap_hive_token.balance}")

            # Check if there's enough of the target token to use for buying
            if swap_hive_token.balance <= min_swap_hive_amount:
                logger.info(
                    f"[{account_name}] Not enough {target_token} to buy tokens (minimum: {min_swap_hive_amount})."
                )
                continue

            # Calculate how much of the target token to use
            use_amount = swap_hive_token.balance
            if max_swap_hive_amount is not None and use_amount > max_swap_hive_amount:
                logger.info(
                    f"[{account_name}] Limiting {target_token} to use from {use_amount:.6f} to max_amount={max_swap_hive_amount:.6f}"
                )
                use_amount = max_swap_hive_amount

            # Get market data for the token we want to buy
            _, lowest_ask = account_trader.get_market_price(token_symbol)
            if lowest_ask <= 0:
                logger.warning(f"[{account_name}] No sellers for {token_symbol}, skipping.")
                continue

            # Calculate how many tokens we can buy with our SWAP.HIVE
            buy_amount = use_amount / lowest_ask
            logger.info(
                f"[{account_name}] Buying {buy_amount:.6f} {token_symbol} for {use_amount:.6f} {target_token} at {lowest_ask:.6f} {target_token}/{token_symbol}"
            )

            # Execute the buy
            if account_trader.buy_token(
                token_symbol,
                buy_amount,
                lowest_ask,
            ):
                if dry_run:
                    logger.info(
                        f"[DRY RUN] Would buy {buy_amount:.6f} {token_symbol} at {lowest_ask:.8f} {target_token} for {account_name} using authority of {main_account_name}."
                    )
                else:
                    logger.info(
                        f"[{account_name}] {token_symbol} bought successfully at {lowest_ask:.8f} {target_token} using authority of {main_account_name}."
                    )
                # Count each successful token buy
                success_count += 1
                account_success = True
            else:
                logger.error(f"[{account_name}] Failed to buy {token_symbol}.")
                continue

            # If we had any successful buys for this account, increment the account counter
            if account_success:
                processed_accounts += 1

        except Exception as e:
            logger.error(f"Error processing account {account_name}: {type(e).__name__}: {e}")
            logger.debug(traceback.format_exc())

    # Report both token buys and account statistics
    logger.info(
        f"Successfully bought {success_count} tokens for {processed_accounts} out of {len(accounts)} accounts"
    )


def main() -> None:
    """
    Main entry point for the Hive-Engine Token Market Trader script.
    Parses command-line arguments, loads the active key, connects to Hive-Engine,
    and trades tokens for all accounts in the configuration based on the operation mode.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Trade Hive-Engine tokens for multiple Hive accounts using a single active key"
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
        help="Token symbol to trade (e.g., SWAP.BTC, LEO, etc.). Not required if --all-tokens is used.",
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
        help="Minimum amount to trigger a trade operation (default: 0.00001)",
    )
    parser.add_argument(
        "-x",
        "--max-amount",
        type=float,
        default=None,
        help="Maximum amount to trade in one run (default: no limit)",
    )
    parser.add_argument(
        "--target",
        default="SWAP.HIVE",
        help="Target token to trade with (default: SWAP.HIVE)",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "-o",
        "--operation",
        choices=["sell", "buy", "stake"],
        default="sell",
        help="Operation mode: 'sell' tokens for SWAP.HIVE, 'buy' tokens with SWAP.HIVE, or 'stake' tokens (default: sell)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate trading tokens without broadcasting",
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

    # Convert whitelist tokens to uppercase
    if whitelist:
        whitelist = [token.upper() for token in whitelist]

    if args.all_tokens:
        logger.info(f"Using whitelist from config: {whitelist}")
        token_symbol = ""  # Not used in sell-all mode
    else:
        token_symbol = args.token.upper() if args.token else ""

    # Execute the requested operation
    operation = args.operation

    if operation == "sell":
        logger.info("Operation mode: Selling tokens for SWAP.HIVE")
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
    elif operation == "buy":
        # For buy operations, we don't support the --all-tokens flag
        if args.all_tokens:
            logger.error("The --all-tokens flag is not supported for buy operations")
            sys.exit(1)

        if not args.token:
            logger.error("The --token flag is required for buy operations")
            sys.exit(1)

        logger.info("Operation mode: Buying tokens with SWAP.HIVE")
        buy_he_tokens_for_all_accounts(
            accounts,
            main_account_name,
            active_key,
            token_symbol,
            args.min_amount,
            args.max_amount,
            args.target,
            dry_run=args.dry_run,
        )
    elif operation == "stake":
        # For stake, either token or all tokens supported
        if not args.all_tokens and not args.token:
            logger.error("Either --token or --all-tokens must be specified for stake operations")
            sys.exit(1)

        logger.info("Operation mode: Staking tokens")
        stake_he_tokens_for_all_accounts(
            accounts,
            main_account_name,
            active_key,
            token_symbol,
            args.min_amount,
            args.max_amount,
            args.target,
            stake_all=args.all_tokens,
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
