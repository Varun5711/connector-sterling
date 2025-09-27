from pathlib import Path
import yaml

_cfg_cache = None

def load_config():
    global _cfg_cache
    if _cfg_cache is not None:
        return _cfg_cache

    root = Path(__file__).resolve().parents[1]
    for fname in ("config.yaml", "config.yml"):
        cfg_path = root / "config" / fname
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                _cfg_cache = yaml.safe_load(f)
                return _cfg_cache
    raise FileNotFoundError("No config.yaml or config.yml found")

def get_secret(key: str, default=None):
    cfg = load_config()
    return cfg.get("secrets", {}).get(key, default)
