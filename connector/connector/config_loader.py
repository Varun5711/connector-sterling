from pathlib import Path
import yaml
import os

BASE = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = BASE / "config" / "config.yaml"

def load_config(path: str | None = None):
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_secret(name: str):
    """
    Production: replace with KeyVault / Vault retrieval.
    For PoC this reads environment variables.
    """
    return os.environ.get(name)