"""HTTP layer for hepsiburada_mcp — Chrome TLS impersonation required.

hepsiburada.com returns HTTP 403 to plain curl/httpx with a browser UA
(verified live 2026-11-06: 403 on homepage AND search with plain curl),
but answers HTTP 200 to curl-cffi chrome120 impersonation. There is no
public JSON API and no login involved — the site is server-rendered HTML,
so the transport must impersonate a real browser at the TLS level.
Requests are kept gentle (one at a time, ~0.8s apart) and read-only.
"""
from __future__ import annotations

import time
from urllib.parse import quote_plus, urlparse

from curl_cffi import requests as _r

BASE = "https://www.hepsiburada.com"
TIMEOUT = 30.0
MIN_INTERVAL = 0.8  # seconds between requests — be polite

_HEADERS = {
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

_last_fetch = 0.0


class HepsiburadaError(RuntimeError):
    pass


def _get(url: str) -> str:
    global _last_fetch
    wait = MIN_INTERVAL - (time.monotonic() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = _r.get(url, impersonate="chrome120", headers=_HEADERS, timeout=TIMEOUT)
    except Exception as e:
        raise HepsiburadaError(f"network error fetching {url}: {e}") from e
    finally:
        _last_fetch = time.monotonic()
    if resp.status_code == 403:
        raise HepsiburadaError(
            "hepsiburada.com refused the request (HTTP 403, bot wall) — try again later"
        )
    if resp.status_code == 429:
        raise HepsiburadaError(
            "hepsiburada.com rate-limited the request (HTTP 429) — try again later"
        )
    if resp.status_code == 404:
        raise HepsiburadaError(f"page not found (HTTP 404): {url}")
    if resp.status_code != 200:
        raise HepsiburadaError(f"unexpected HTTP {resp.status_code} fetching {url}")
    return resp.text


def fetch_search_html(query: str, sort_param: str | None = None, page: int = 1) -> str:
    """Search page HTML. sort_param: 'artanfiyat' (price asc) or 'azalanfiyat' (price desc)."""
    url = f"{BASE}/ara?q={quote_plus(query)}"
    if sort_param:
        url += f"&siralama={sort_param}"
    if page > 1:
        url += f"&sayfa={page}"
    return _get(url)


def fetch_product_html(product: str) -> str:
    """Product page HTML. product: full URL, site path, or 'slug-p-HBCV…' path."""
    path = product.strip()
    if path.startswith("http"):
        parsed = urlparse(path)
        if "hepsiburada.com" not in parsed.netloc:
            raise HepsiburadaError("product must be a hepsiburada.com URL or path")
        path = parsed.path
    if not path.startswith("/"):
        path = "/" + path
    if "-p-HBCV" not in path:
        raise HepsiburadaError(
            "product must be a product URL/path containing '-p-HBCV…' "
            "(find one with hepsiburada_search first)"
        )
    return _get(f"{BASE}{path}")


def fetch_home_html() -> str:
    return _get(f"{BASE}/")
