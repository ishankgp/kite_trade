import os
from pathlib import Path
from typing import Optional

_DOTENV_USED = False

def load_env(dotenv_path: Optional[str] = None):
    """Load environment variables.

    Priority:
    1. Existing os.environ values (never overwritten)
    2. python-dotenv (if installed)
    3. Fallback simple parser
    """
    global _DOTENV_USED
    if dotenv_path is None:
        dotenv_path = Path(__file__).parent / '.env'
    else:
        dotenv_path = Path(dotenv_path)

    # Try python-dotenv first
    if not _DOTENV_USED:
        try:
            from dotenv import load_dotenv as _ld
            _ld(dotenv_path, override=False)
            _DOTENV_USED = True
            return
        except Exception:
            # Fall back to manual parsing
            pass

    if not dotenv_path.exists():
        return
    try:
        for line in dotenv_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        return


def get_kite_config():
    """Return a dict with Kite configuration pulled from environment.
    Required: KITE_API_KEY, KITE_API_SECRET, KITE_REDIRECT_URL.
    """
    load_env()
    cfg = {
        'api_key': os.environ.get('KITE_API_KEY'),
        'api_secret': os.environ.get('KITE_API_SECRET'),
        'redirect_url': os.environ.get('KITE_REDIRECT_URL'),
        'postback_url': os.environ.get('KITE_POSTBACK_URL'),
        'debug': os.environ.get('KITE_DEBUG', 'false').lower() == 'true'
    }
    missing = [k for k, v in cfg.items() if k in ['api_key', 'api_secret', 'redirect_url'] and not v]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    return cfg
