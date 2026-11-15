"""Local-session account actions (cart + favorites) for hepsiburada_mcp.

Session model: the user pastes their raw Cookie header value (copied
from their browser DevTools) into the HEPSIBURADA_SESSION env var in
their MCP client config. The server reads it from os.environ at call
time (not import time). The session never leaves the user's machine
except to hepsiburada.com hosts: it is never logged, printed,
persisted, or included in any tool output or error message — not even
redacted fragments. Refreshed cookies live only in process memory.

Endpoints (reverse-engineered from Hepsiburada's public JS bundles and
verified live 2026-11-15 via unauthenticated probes — every endpoint
below returned HTTP 401 {"Message":"Invalid Token"} without a session,
proving the path + auth gate; the XSRF endpoint returned 200):
- Checkout API  https://checkout.hepsiburada.com/api
  PUT /basket (add to cart; POST is wrong — it hits a WAF tarpit)
- Basket web API https://checkout.hepsiburada.com/web/api/v1
  GET /basket/all, DELETE /basket/item/{id}, PATCH /basket/item/{id}
- Favorites BFF https://favorites-bff.hepsiburada.com/v1
  GET /favorite-skus, POST /favorites, DELETE /favorites/{sku}
- OAuth https://oauth.hepsiburada.com/api/authenticate
  GET /xsrf-token, POST /refresh-token

tenant-id / client-id are PUBLIC constants embedded in Hepsiburada's
public JS bundles — not secrets.

Response shapes are UNVERIFIED without a live account, so all parsing
here is defensive: unknown shapes return an explicit note, never
fabricated data. Deliberately NOT implemented: clear-basket DELETEs,
checkout/payment, giftcert/coupons, bulk add, bulk delete.
"""
from __future__ import annotations

import json
import os
import re
import time
from urllib.parse import quote

from curl_cffi import requests as _r

from . import http as _http
from . import products as _P

SESSION_ENV = "HEPSIBURADA_SESSION"

CHECKOUT_API = "https://checkout.hepsiburada.com/api"
BASKET_WEB_API = "https://checkout.hepsiburada.com/web/api/v1"
FAVORITES_API = "https://favorites-bff.hepsiburada.com/v1"
OAUTH_API = "https://oauth.hepsiburada.com/api/authenticate"

# Public constants embedded in Hepsiburada's public JS bundles — not secrets.
TENANT_ID = "cc7c5241-6017-44b2-9528-93c8d8907efb"
CLIENT_ID = "47b14cfb-2cad-471a-85de-ebe4684ee95f"

CART_URL = "https://checkout.hepsiburada.com/"
FAVORITES_URL = "https://listelerim.hepsiburada.com"

TIMEOUT = 30.0
MIN_INTERVAL = 0.8  # seconds between requests — be polite

_NO_SESSION_MSG = (
    "HEPSIBURADA_SESSION is not configured — account actions need your "
    "browser session cookie. See README 'Account actions' for setup."
)
_EXPIRED_MSG = (
    "session expired — copy fresh cookies from your browser "
    "(see README 'Account actions')"
)

_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class AccountError(RuntimeError):
    """Account-action failure. Never carries session material."""


class SessionNotConfigured(AccountError):
    pass


class SessionExpired(AccountError):
    pass


# ---------------------------------------------------------------- session

def _parse_cookie_header(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies[name.strip()] = value.strip()
    return cookies


class Session:
    """In-memory holder for the user's browser session cookies.

    Refreshed cookies are adopted into _overrides (process memory only,
    never persisted). The raw env value is never stored or exposed.
    """

    def __init__(self, raw: str):
        self.cookies = _parse_cookie_header(raw)
        self._overrides: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self._overrides.get(name, self.cookies.get(name))

    def adopt(self, name: str, value: str) -> None:
        self._overrides[name] = value

    def cookie_header(self) -> str:
        merged = {**self.cookies, **self._overrides}
        return "; ".join(f"{k}={v}" for k, v in merged.items())


def get_session() -> Session:
    """Read the session from the environment at call time."""
    raw = os.environ.get(SESSION_ENV, "").strip()
    if not raw:
        raise SessionNotConfigured(_NO_SESSION_MSG)
    return Session(raw)


# ---------------------------------------------------------------- transport

_PROFILES = ("chrome120", "chrome131", "safari17_0")
_MAX_ATTEMPTS = 2  # one retry with the next profile
_RETRY_BACKOFF = 1.0  # seconds between attempts
_profile_idx = 0  # sticky: profile that last succeeded
_last_fetch = 0.0


def _throttle() -> None:
    global _last_fetch
    wait = MIN_INTERVAL - (time.monotonic() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    _last_fetch = time.monotonic()


def _raw_request(method: str, url: str, headers: dict, json_body=None):
    """One HTTP call with Chrome TLS impersonation + profile rotation.

    Returns the curl_cffi response. Tests monkeypatch this function.
    Retries (once, next profile) on HTTP 403/429 — the server rejected
    the request, so retrying is safe even for mutations. Transport
    errors retry only for GET: a failed mutating call may already have
    been applied server-side.
    """
    global _profile_idx
    _throttle()
    last_exc: Exception | None = None
    for k in range(_MAX_ATTEMPTS):
        profile = _PROFILES[(_profile_idx + k) % len(_PROFILES)]
        try:
            resp = _r.request(
                method, url, impersonate=profile, headers=headers,
                json=json_body, timeout=TIMEOUT,
            )
        except Exception as e:
            last_exc = e
            if method == "GET" and k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            raise AccountError(
                f"network error calling hepsiburada API: {e}"
            ) from e
        if resp.status_code in (403, 429):
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            return resp
        _profile_idx = (_profile_idx + k) % len(_PROFILES)
        return resp
    raise AccountError(
        f"network error calling hepsiburada API: {last_exc}"
    ) from last_exc


def _parse_json_body(resp):
    """Parsed JSON body, or None when the body is empty / not JSON."""
    try:
        text = resp.text
    except Exception:
        return None
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _server_message(resp) -> str:
    """Short server error message (e.g. "Invalid Token"), if any.

    Only the Message field is surfaced, truncated — never the full body.
    """
    data = _parse_json_body(resp)
    if isinstance(data, dict):
        msg = data.get("Message") or data.get("message")
        if isinstance(msg, str) and msg:
            return msg[:200]
    return ""


def _handle_response(resp, endpoint: str):
    """Map an HTTP response to parsed JSON or a safe AccountError."""
    status = resp.status_code
    if 200 <= status < 300:
        data = _parse_json_body(resp)
        return data if data is not None else {}
    if status == 401:
        raise SessionExpired(_EXPIRED_MSG)
    if status == 403:
        raise AccountError(
            f"{endpoint} refused the request (HTTP 403) — the session may "
            "lack access or the request was blocked"
        )
    if status == 429:
        raise AccountError(
            f"{endpoint} rate-limited the request (HTTP 429) — try again later"
        )
    msg = _server_message(resp)
    raise AccountError(
        f"{endpoint} returned unexpected HTTP {status}"
        + (f": {msg}" if msg else "")
    )


# ---------------------------------------------------------------- auth headers

def _checkout_headers(session: Session) -> dict:
    headers = {
        "tenant-id": TENANT_ID,
        "client-id": CLIENT_ID,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Cookie": session.cookie_header(),
    }
    jwt = session.get("jwt")
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    anon = session.get("hbus_anonymousId")
    if anon:
        headers["anonymous-user-id"] = anon
    device = session.get("uniqueDeviceId")
    if device:
        headers["unique-device-id"] = device
    location = session.get("location")
    if location:
        headers["location-of-customer"] = location
    return headers


def _basket_web_headers(session: Session) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Cookie": session.cookie_header(),
    }
    hp_jwt = session.get("hpJwtToken")
    if hp_jwt:
        headers["HPBearer"] = hp_jwt
    anon = session.get("hbus_anonymousId")
    if anon:
        headers["anonymous-user-id"] = anon
    return headers


def _favorites_headers(session: Session) -> dict:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Cookie": session.cookie_header(),
    }


# ---------------------------------------------------------------- xsrf + refresh

_xsrf_token: str | None = None  # process lifetime only, never persisted


def _fetch_xsrf_token(session: Session, force: bool = False) -> str:
    """GET the XSRF token (cached for the process lifetime).

    Raises AccountError when the fetch fails — the caller must not guess.
    """
    global _xsrf_token
    if _xsrf_token and not force:
        return _xsrf_token
    headers = {"Cookie": session.cookie_header(), "Accept": "application/json"}
    resp = _raw_request("GET", f"{OAUTH_API}/xsrf-token", headers)
    if resp.status_code == 401:
        raise SessionExpired(_EXPIRED_MSG)
    if resp.status_code != 200:
        raise AccountError(
            f"could not fetch XSRF token (HTTP {resp.status_code})"
        )
    data = _parse_json_body(resp)
    token = data.get("xsrfToken") if isinstance(data, dict) else None
    if not token:
        raise AccountError("could not fetch XSRF token (unexpected response)")
    _xsrf_token = token
    return token


def _adopt_set_cookies(session: Session, resp) -> bool:
    """Adopt jwt/hpJwtToken from Set-Cookie headers, if actually present.

    Returns True when at least one session cookie was adopted.
    """
    raw_list: list[str] = []
    headers = resp.headers
    get_list = getattr(headers, "get_list", None)
    if callable(get_list):
        try:
            raw_list = get_list("set-cookie") or []
        except Exception:
            raw_list = []
    if not raw_list:
        single = headers.get("set-cookie") if hasattr(headers, "get") else None
        if single:
            raw_list = [single]
    adopted = False
    for raw in raw_list:
        first = raw.split(";", 1)[0].strip()
        if "=" not in first:
            continue
        name, value = first.split("=", 1)
        name, value = name.strip(), value.strip()
        if name in ("jwt", "hpJwtToken") and value:
            session.adopt(name, value)
            adopted = True
    return adopted


def _refresh(session: Session) -> bool:
    """One refresh attempt. True only when new cookies were adopted."""
    try:
        token = _fetch_xsrf_token(session)
    except AccountError:
        return False
    headers = {
        "Cookie": session.cookie_header(),
        "X-XSRF-TOKEN": token,
        "Accept": "application/json",
    }
    try:
        resp = _raw_request("POST", f"{OAUTH_API}/refresh-token", headers)
    except AccountError:
        return False
    if resp.status_code != 200:
        return False
    return _adopt_set_cookies(session, resp)


def _authed(method, url, session, build_headers, json_body=None,
            xsrf=False, endpoint="hepsiburada API"):
    """Authed API call with one refresh retry on 401 and (favorites only)
    one XSRF re-fetch retry on 403. Returns parsed JSON (dict/list) or {}.

    build_headers is a callable taking the session, so refreshed cookies
    are picked up on retry.
    """
    refreshed = False
    xsrf_retried = False
    while True:
        headers = build_headers(session)
        if xsrf:
            headers["X-XSRF-TOKEN"] = _fetch_xsrf_token(
                session, force=xsrf_retried
            )
        resp = _raw_request(method, url, headers, json_body)
        if resp.status_code == 401 and not refreshed:
            refreshed = True
            if _refresh(session):
                continue
            raise SessionExpired(_EXPIRED_MSG)
        if resp.status_code == 403 and xsrf and not xsrf_retried:
            xsrf_retried = True
            continue
        return _handle_response(resp, endpoint)


# ---------------------------------------------------------------- validation

def _validate_quantity(quantity) -> int:
    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or not 1 <= quantity <= 99
    ):
        raise ValueError("quantity must be an integer between 1 and 99")
    return quantity


def _validate_basket_type(basket_type: str) -> str:
    if basket_type not in ("Primary", "Secondary"):
        raise ValueError("basket_type must be 'Primary' or 'Secondary'")
    return basket_type


def _validate_guid(value, name: str) -> str:
    if not isinstance(value, str) or not _GUID_RE.match(value.strip()):
        raise ValueError(
            f"{name} must be a GUID (e.g. 'd582621c-3b3b-45b3-821e-70d39621f933')"
        )
    return value.strip()


# ---------------------------------------------------------------- defensive parsers

_ITEM_ID_KEYS = ("basketItemId", "id", "basketItemID")
_SKU_KEYS = ("sku", "productSku")
_NAME_KEYS = ("name", "title", "productName")
_QTY_KEYS = ("quantity", "count")
_PRICE_KEYS = ("price", "totalPrice", "salePrice", "unitPrice")
_MERCHANT_KEYS = ("merchant", "merchantName", "sellerName")


def _first(d, keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d.get(k)
    return None


def parse_basket(data) -> dict:
    """Defensive parse of GET /basket/all (shape unverified without a
    live account). Never fabricates items: an unrecognized shape returns
    an explicit note with the top-level keys."""
    container = data
    if isinstance(data, dict):
        for wrapper in ("result", "data"):
            inner = data.get(wrapper)
            if isinstance(inner, (dict, list)):
                container = inner
                break
    items: list[dict] = []
    total_price = None
    recognized = False
    if isinstance(container, list):
        raw_items = [(it, None) for it in container]
        recognized = True
    elif isinstance(container, dict):
        raw_items: list[tuple] = []
        for key in ("items", "basketItems", "products", "basketProducts"):
            if isinstance(container.get(key), list):
                raw_items = [(it, None) for it in container[key]]
                recognized = True
                break
        if not raw_items:
            selected = container.get("selectedItems")
            if selected is None:
                selected = container.get("primaryItems")
            unselected = container.get("unselectedItems")
            if unselected is None:
                unselected = container.get("secondaryItems")
            if isinstance(selected, list):
                raw_items += [(it, True) for it in selected]
                recognized = True
            if isinstance(unselected, list):
                raw_items += [(it, False) for it in unselected]
                recognized = True
        total_price = _first(container, ("totalPrice", "basketTotal", "totalAmount"))
        if isinstance(total_price, dict):
            total_price = total_price.get("value") or total_price.get("amount")
    else:
        raw_items = []
    if not recognized:
        return {
            "items": [],
            "note": "unexpected response shape",
            "response_keys": list(data.keys()) if isinstance(data, dict) else [],
        }
    for item, forced_selected in raw_items:
        if not isinstance(item, dict):
            continue
        row: dict = {}
        basket_item_id = _first(item, _ITEM_ID_KEYS)
        if basket_item_id is not None:
            row["basket_item_id"] = str(basket_item_id)
        sku = _first(item, _SKU_KEYS)
        if sku is not None:
            row["sku"] = str(sku)
        name = _first(item, _NAME_KEYS)
        if name is not None:
            row["name"] = str(name)
        qty = _first(item, _QTY_KEYS)
        if qty is not None:
            try:
                row["quantity"] = int(qty)
            except (TypeError, ValueError):
                pass
        price = _first(item, _PRICE_KEYS)
        if isinstance(price, dict):
            price = price.get("value") or price.get("amount")
        if price is not None:
            try:
                row["price_try"] = float(price)
            except (TypeError, ValueError):
                pass
        selected = forced_selected
        if selected is None:
            selected = item.get("isSelected")
            if selected is None:
                selected = item.get("selected")
        if isinstance(selected, bool):
            row["is_selected"] = selected
        merchant = _first(item, _MERCHANT_KEYS)
        if isinstance(merchant, dict):
            merchant = merchant.get("name")
        if merchant is not None:
            row["merchant"] = str(merchant)
        items.append(row)
    out: dict = {
        "items": items,
        "total_item_count": sum(i.get("quantity", 1) for i in items),
    }
    if total_price is not None:
        try:
            out["total_price_try"] = float(total_price)
        except (TypeError, ValueError):
            pass
    return out


def parse_favorite_skus(data) -> dict:
    """Defensive parse of GET /favorite-skus: accepts a bare list, or
    {"skus": [...]}, {"data": [...]}, {"favoriteSkus": [...]} (the JS
    client unwraps a {success, data} envelope). Unknown shape → note."""
    skus = None
    if isinstance(data, list):
        skus = data
    elif isinstance(data, dict):
        for key in ("skus", "data", "favoriteSkus", "favorite_skus"):
            if isinstance(data.get(key), list):
                skus = data[key]
                break
        if skus is None and isinstance(data.get("result"), dict):
            for key in ("skus", "data", "favoriteSkus", "favorite_skus"):
                if isinstance(data["result"].get(key), list):
                    skus = data["result"][key]
                    break
    if skus is None:
        return {
            "skus": [],
            "note": "unexpected response shape",
            "response_keys": list(data.keys()) if isinstance(data, dict) else [],
        }
    clean: list[str] = []
    for entry in skus:
        if isinstance(entry, str):
            clean.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("sku"), str):
            clean.append(entry["sku"])
    return {"skus": clean, "count": len(clean)}


# ---------------------------------------------------------------- operations

def _resolve_product(product_url: str):
    """Fetch a product page; return (detail dict, listing-info dict)."""
    html = _http.fetch_product_html(product_url)
    detail = _P.parse_product_detail(html)
    info = _P.parse_listing_info(html, sku=detail.get("sku"))
    return detail, info


def view_cart() -> dict:
    session = get_session()
    data = _authed(
        "GET", f"{BASKET_WEB_API}/basket/all", session,
        _basket_web_headers, endpoint="view cart",
    )
    result = parse_basket(data)
    result["cart_url"] = CART_URL
    return result


def add_to_cart(sku: str, listing_id: str | None = None,
                product_url: str | None = None, quantity: int = 1) -> dict:
    _validate_quantity(quantity)
    session = get_session()
    metadata: dict = {"sku": sku}
    if listing_id:
        metadata["listingId"] = listing_id
    if product_url:
        detail, info = _resolve_product(product_url)
        if "listingId" not in metadata and info.get("listing_id"):
            metadata["listingId"] = info["listing_id"]
        if detail.get("name"):
            metadata["name"] = detail["name"]
        images = detail.get("images") or []
        if images:
            metadata["imageUrl"] = images[0]
    if "listingId" not in metadata:
        raise AccountError(
            "listing_id is required to add to cart — call "
            "hepsiburada_product_detail with the product URL to get "
            "listing_id, or pass product_url"
        )
    body = {
        "product": {
            "metadata": metadata,
            "quantity": quantity,
            "origin": "SfProductDetail",
        }
    }
    data = _authed(
        "PUT", f"{CHECKOUT_API}/basket", session, _checkout_headers,
        json_body=body, endpoint="add to cart",
    )
    out: dict = {
        "added": True,
        "sku": sku,
        "quantity": quantity,
        "cart_url": CART_URL,
    }
    if isinstance(data, dict):
        result = data.get("result") if isinstance(data.get("result"), dict) else data
        count = result.get("totalBasketItemCount")
        if isinstance(count, int):
            out["total_basket_item_count"] = count
        messages = data.get("messages") or result.get("messages")
        if messages:
            out["messages"] = messages
    return out


def remove_from_cart(basket_item_id: str, basket_type: str = "Primary") -> dict:
    _validate_guid(basket_item_id, "basket_item_id")
    _validate_basket_type(basket_type)
    session = get_session()

    def _headers(s: Session) -> dict:
        headers = _basket_web_headers(s)
        headers["basket-type"] = basket_type
        return headers

    _authed(
        "DELETE",
        f"{BASKET_WEB_API}/basket/item/{quote(basket_item_id, safe='')}",
        session, _headers, endpoint="remove from cart",
    )
    return {
        "removed": True,
        "basket_item_id": basket_item_id,
        "cart_url": CART_URL,
    }


def update_cart_quantity(basket_item_id: str, quantity: int,
                         basket_type: str = "Primary") -> dict:
    if quantity == 0:
        raise ValueError(
            "quantity 0 is not a supported removal path — use "
            "hepsiburada_remove_from_cart instead"
        )
    _validate_quantity(quantity)
    _validate_guid(basket_item_id, "basket_item_id")
    _validate_basket_type(basket_type)
    session = get_session()

    def _headers(s: Session) -> dict:
        headers = _basket_web_headers(s)
        headers["basket-type"] = basket_type
        return headers

    body = [{"value": quantity, "path": "/Quantity", "op": "replace", "from": "int"}]
    _authed(
        "PATCH",
        f"{BASKET_WEB_API}/basket/item/{quote(basket_item_id, safe='')}",
        session, _headers, json_body=body, endpoint="update cart quantity",
    )
    return {
        "updated": True,
        "basket_item_id": basket_item_id,
        "quantity": quantity,
        "cart_url": CART_URL,
    }


def list_favorites() -> dict:
    session = get_session()
    data = _authed(
        "GET", f"{FAVORITES_API}/favorite-skus", session,
        _favorites_headers, endpoint="list favorites",
    )
    result = parse_favorite_skus(data)
    result["favorites_url"] = FAVORITES_URL
    return result


def add_favorite(sku: str, listing_id: str | None = None,
                 product_id: str | None = None,
                 product_url: str | None = None) -> dict:
    session = get_session()
    if product_url:
        _detail, info = _resolve_product(product_url)
        listing_id = listing_id or info.get("listing_id")
        product_id = product_id or info.get("product_id")
    if not listing_id or not product_id:
        raise AccountError(
            "listing_id and product_id are required to add a favorite — "
            "call hepsiburada_product_detail with the product URL to get "
            "them, or pass product_url"
        )
    body = {"sku": sku, "listingId": listing_id, "productId": product_id}
    _authed(
        "POST", f"{FAVORITES_API}/favorites", session, _favorites_headers,
        json_body=body, xsrf=True, endpoint="add favorite",
    )
    return {"added": True, "sku": sku, "favorites_url": FAVORITES_URL}


def remove_favorite(sku: str) -> dict:
    session = get_session()
    _authed(
        "DELETE", f"{FAVORITES_API}/favorites/{quote(sku, safe='')}",
        session, _favorites_headers, xsrf=True, endpoint="remove favorite",
    )
    return {"removed": True, "sku": sku, "favorites_url": FAVORITES_URL}
