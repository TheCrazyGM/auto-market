"""
Configuration handling for Hive market trading scripts.
Handles loading accounts and API keys from YAML files or environment variables.
"""

import logging
import os
import sys
from typing import List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


def load_accounts_and_active_key(
    accounts_path: Optional[str] = None,
) -> Tuple[List[str], Optional[str], List[str]]:
    """
    Load accounts list, active key, and whitelist from YAML file.

    Args:
        accounts_path: Path to YAML config file. If None, tries accounts.yaml in current directory.

    Returns:
        Tuple of (list of account names, active key, whitelist)

    Raises:
        SystemExit: If no account list is found or there's an error loading the file.
    """
    if accounts_path:
        try:
            with open(accounts_path, "r") as f:
                data = yaml.safe_load(f)
            logger.info(f"Loaded accounts and active key from {accounts_path}")
            return data.get("accounts", []), data.get("active_key"), data.get("whitelist", [])
        except Exception as e:
            logger.error(f"Failed to load accounts from {accounts_path}: {e}")
            sys.exit(1)

    # Try default accounts.yaml
    if os.path.exists("accounts.yaml"):
        try:
            with open("accounts.yaml", "r") as f:
                data = yaml.safe_load(f)
            logger.info("Loaded accounts and active key from accounts.yaml")
            return data.get("accounts", []), data.get("active_key"), data.get("whitelist", [])
        except Exception as e:
            logger.error(f"Failed to load accounts from accounts.yaml: {e}")
            sys.exit(1)

    logger.error(
        "No account list found. Please provide --accounts or create accounts.yaml in the current directory."
    )
    sys.exit(1)


def get_active_key(
    cli_active_key: Optional[str] = None, yaml_active_key: Optional[str] = None
) -> str:
    """
    Retrieve and validate the active key from CLI, YAML, or environment variables.

    Args:
        cli_active_key: Active key from command-line argument.
        yaml_active_key: Active key from YAML config.

    Returns:
        The active key.

    Raises:
        SystemExit: If no active key is found.
    """
    logger.debug(
        f"Attempting to retrieve active key (cli_active_key provided: {bool(cli_active_key)}, "
        f"yaml_active_key provided: {bool(yaml_active_key)})"
    )

    if cli_active_key:
        logger.info("Using active key from --active-key argument.")
        active_key = cli_active_key
    elif yaml_active_key:
        logger.info("Using active key from YAML config file.")
        active_key = yaml_active_key
    else:
        active_key = os.getenv("ACTIVE_WIF")
        if active_key:
            logger.info("Using active key from ACTIVE_WIF environment variable.")

    if not active_key:
        logger.error(
            "Active key must be provided via --active-key, YAML config, or ACTIVE_WIF env variable."
        )
        sys.exit(1)

    logger.debug("Active key successfully retrieved.")
    return active_key
