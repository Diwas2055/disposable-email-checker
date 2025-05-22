import json
import logging
from pathlib import Path
from typing import Set

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def load_domains(file_path: str) -> Set[str]:
    """Load domains from a JSON file into a set"""
    path = Path(file_path)
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directories exist
            path.write_text("[]")  # Create an empty list in JSON format
            logger.info(f"Created new domain file at {file_path}")
        except Exception as e:
            logger.error(f"Failed to create domain file {file_path}: {e}")
            return set()
    try:
        with path.open("r") as f:
            return set(json.load(f))
    except Exception as e:
        logger.error(f"Failed to load domains from {file_path}: {e}")
        return set()


def write_domains(file_path: str, domains: Set[str]):
    """Write domains to a JSON file from a set"""
    try:
        with open(file_path, "w") as f:
            json.dump(sorted(list(domains)), f, indent=2)
        logger.info(f"Saved {len(domains)} domains to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save domains to {file_path}: {e}")
