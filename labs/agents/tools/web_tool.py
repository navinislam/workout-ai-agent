import requests
from . import __init__  # noqa
from ..policies import ALLOWED_HOSTS, REQUEST_TIMEOUT_S


def web_fetch(url: str, max_bytes: int = 20000) -> str:
    if not any(url.startswith(prefix) for prefix in ALLOWED_HOSTS):
        raise ValueError("URL not allowed by policy")
    r = requests.get(url, timeout=REQUEST_TIMEOUT_S)
    r.raise_for_status()
    text = r.text
    return text[:max_bytes]

