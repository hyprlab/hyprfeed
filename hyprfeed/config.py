import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _secret_key() -> str:
    """Use SECRET_KEY from the environment, otherwise persist one in the data dir
    so sessions survive restarts."""
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    keyfile = DATA_DIR / ".secret_key"
    if keyfile.exists():
        return keyfile.read_text().strip()
    key = secrets.token_hex(32)
    keyfile.write_text(key)
    keyfile.chmod(0o600)
    return key


class Config:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DATA_DIR / 'hyprfeed.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Cloudflare Turnstile — leave unset to disable the challenge (e.g. local dev).
    TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
    TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")

    ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "1") != "0"

    # Background refresh cadence, in minutes. 0 disables the refresher thread.
    REFRESH_MINUTES = int(os.environ.get("REFRESH_MINUTES", "15"))

    ENTRIES_PER_PAGE = 36
    # Per-feed retention: older entries beyond this are pruned on refresh.
    MAX_ENTRIES_PER_FEED = int(os.environ.get("MAX_ENTRIES_PER_FEED", "300"))
