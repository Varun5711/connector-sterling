import os, yaml
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = BASE.parent / "config" / "config.yaml"

def load_config(path=None):
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_secret(name: str):
    return os.environ.get(name)  # in prod: use Vault/KeyVault