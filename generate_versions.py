#!/usr/bin/env python3
"""Generate version files for NectarCache package."""

import os
import re


def get_version():
    """Get version from pyproject.toml."""
    # Use regex to extract version from pyproject.toml
    with open("pyproject.toml", "r") as f:
        content = f.read()
        version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
        if version_match:
            return version_match.group(1)
        raise ValueError("Could not find version in pyproject.toml")


def update_init_version(filename, version):
    """Update version in __init__.py file."""
    if not os.path.exists(filename):
        print(f"Warning: {filename} does not exist")
        return False

    with open(filename, "r") as file:
        content = file.read()

    # Replace version using regex
    new_content = re.sub(r'__version__\s*=\s*"[^"]*"', f'__version__ = "{version}"', content)

    if new_content == content:
        print(f"No changes needed in {filename}")
        return False

    with open(filename, "w") as file:
        file.write(new_content)

    return True


def main():
    """Main function."""
    version = get_version()
    print(f"Updating version to {version}")

    # Update version in __init__.py
    init_file = "src/auto_market/__init__.py"
    if update_init_version(init_file, version):
        print(f"Updated version in {init_file} to {version}")
    else:
        print(f"No update needed for {init_file}")

    print("Version update completed!")


if __name__ == "__main__":
    main()
