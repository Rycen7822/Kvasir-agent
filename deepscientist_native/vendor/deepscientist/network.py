from __future__ import annotations

import os
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener, urlopen as stdlib_urlopen

try:
    from websockets.sync.client import connect as stdlib_websocket_connect
except ModuleNotFoundError as exc:  # Optional: only needed for websocket attach paths.
    _WEBSOCKETS_IMPORT_ERROR = exc
    stdlib_websocket_connect = None
else:
    _WEBSOCKETS_IMPORT_ERROR = None

_RUNTIME_PROXY_URL: str | None = None
_NO_PROXY_OPENER = build_opener(ProxyHandler({}))
_PROXY_OPENERS: dict[str, object] = {}


def normalize_proxy_url(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def configure_runtime_proxy(proxy_url: str | None) -> str | None:
    normalized = normalize_proxy_url(proxy_url)
    global _RUNTIME_PROXY_URL
    previous = _RUNTIME_PROXY_URL
    _RUNTIME_PROXY_URL = normalized
    if normalized is None:
        if previous is not None:
            for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                if os.environ.get(key) == previous:
                    os.environ.pop(key, None)
        return None
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ[key] = normalized
    # Keep local loopback websocket attaches off the proxy path.
    for key in ("NO_PROXY", "no_proxy"):
        current = str(os.environ.get(key) or "").strip()
        values = [item.strip() for item in current.split(",") if item.strip()]
        for host in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
            if host not in values:
                values.append(host)
        os.environ[key] = ",".join(values)
    return normalized


def runtime_proxy_url() -> str | None:
    return _RUNTIME_PROXY_URL


def should_bypass_proxy(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    host = (parsed.hostname or "").strip().lower()
    return host in {"", "127.0.0.1", "localhost", "::1", "0.0.0.0"}


def _proxy_opener(proxy_url: str):
    opener = _PROXY_OPENERS.get(proxy_url)
    if opener is None:
        opener = build_opener(ProxyHandler({"http": proxy_url, "https": proxy_url}))
        _PROXY_OPENERS[proxy_url] = opener
    return opener


def urlopen_with_proxy(request: Request | str, timeout: float | None = None):
    url = request.full_url if isinstance(request, Request) else str(request)
    if should_bypass_proxy(url):
        return _NO_PROXY_OPENER.open(request, timeout=timeout)
    proxy_url = runtime_proxy_url()
    if proxy_url:
        return _proxy_opener(proxy_url).open(request, timeout=timeout)
    return stdlib_urlopen(request, timeout=timeout)


def websocket_connect_with_proxy(uri: str, /, **kwargs):
    if stdlib_websocket_connect is None:
        raise RuntimeError("The optional `websockets` package is required for websocket connections.") from _WEBSOCKETS_IMPORT_ERROR
    if should_bypass_proxy(uri):
        kwargs.setdefault("proxy", None)
    else:
        proxy_url = runtime_proxy_url()
        if proxy_url:
            kwargs.setdefault("proxy", proxy_url)
    return stdlib_websocket_connect(uri, **kwargs)
