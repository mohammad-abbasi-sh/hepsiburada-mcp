"""Stdlib parsing for hepsiburada.com server-rendered pages.

Verified live 2026-11-06 against real pages:
- Search (/ara?q=…): <article class="productCard-module_article__…">
  cards with title link (/-p-HBCV…), final price
  (data-test-id="final-price-N"), rating sr-only text
  ("Ürün puanı 4.8, 13102 değerlendirme"), image, campaign text.
- Product page: schema.org Product JSON-LD inside <script
  type="application/ld+json"> (@graph or top-level list), a
  "Satıcı: <a …>Name</a>" seller block with a "Resmi Satıcı"
  (official seller) badge, and a "Ürün Özellikleri" <ul> of
  highlight bullets. Review items are JSON-LD Review objects.
- Homepage: top-category links /<slug>-c-<id> with Turkish names.
"""
from __future__ import annotations

import html as _html
import json
import re
import statistics

BASE = "https://www.hepsiburada.com"

SORTS = {
    "relevance": None,          # hepsiburada default ("akıllı sıralama")
    "price_asc": "artanfiyat",  # verified live: first prices ascend
    "price_desc": "azalanfiyat",
}


def resolve_sort(sort: str) -> str | None:
    if sort not in SORTS:
        raise ValueError(
            f"unknown sort {sort!r} (expected one of: {', '.join(SORTS)})"
        )
    return SORTS[sort]


def parse_tr_number(text: str) -> float:
    """Turkish number: '56.999' -> 56999.0, '56.999,00' -> 56999.0, '4,8' -> 4.8."""
    s = text.strip().replace("\u00a0", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    return float(s)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


# ---------------------------------------------------------------- search

_CARD_RE = re.compile(
    r'<article class="productCard-module_article__[^"]*">(.*?)</article>', re.S
)
_TITLE_RE = re.compile(r'<a[^>]*\btitle="([^"]+)"')
_HREF_RE = re.compile(r'href="(/[^"]*-p-(HBCV[0-9A-Z]+))"')
_PRICE_RE = re.compile(r'data-test-id="final-price-\d+">\s*([\d\.,]+)')
_ORIG_PRICE_RE = re.compile(
    r"price-module_originalPriceArea__[^>]*>\s*([\d\.,]+)", re.S
)
_RATING_RE = re.compile(r"Ürün puanı\s+([\d,]+),\s*([\d\.]+)\s+değerlendirme")
_RATING_FALLBACK_RE = re.compile(
    r"rate-module_rating__[^>]*>([\d,]+)<"
)
_COUNT_FALLBACK_RE = re.compile(
    r"rate-module_count__[^>]*>\(?<!-- -->([\d\.]+)"
)
_IMAGE_RE = re.compile(r"https://productimages\.hepsiburada\.net[^\"'\s]+")
_CAMPAIGN_RE = re.compile(
    r"campaign-module_campaignText__[^>]*>([^<]+)<"
)
_VARIANTS_RE = re.compile(
    r'data-test-id="variants-count-\d+">(?:<[^>]+>)*\s*(\d+)'
)


def parse_search_results(html: str, limit: int = 10) -> list[dict]:
    """Parse search-page product cards. Returns de-duplicated products."""
    out: list[dict] = []
    seen: set[str] = set()
    for m in _CARD_RE.finditer(html):
        card = m.group(1)
        href_m = _HREF_RE.search(card)
        if not href_m:
            continue
        path, sku = href_m.group(1), href_m.group(2)
        if sku in seen:
            continue
        seen.add(sku)
        title_m = _TITLE_RE.search(card)
        price_m = _PRICE_RE.search(card)
        if not title_m or not price_m:
            continue
        try:
            price = parse_tr_number(price_m.group(1))
        except ValueError:
            continue
        row: dict = {
            "title": _html.unescape(title_m.group(1)).strip(),
            "url": BASE + path,
            "sku": sku,
            "price_try": price,
        }
        orig_m = _ORIG_PRICE_RE.search(card)
        if orig_m:
            try:
                row["original_price_try"] = parse_tr_number(orig_m.group(1))
            except ValueError:
                pass
        rating_m = _RATING_RE.search(card)
        if rating_m:
            try:
                row["rating"] = parse_tr_number(rating_m.group(1))
                row["review_count"] = int(rating_m.group(2).replace(".", ""))
            except ValueError:
                pass
        else:
            rf = _RATING_FALLBACK_RE.search(card)
            cf = _COUNT_FALLBACK_RE.search(card)
            if rf:
                try:
                    row["rating"] = parse_tr_number(rf.group(1))
                except ValueError:
                    pass
            if cf:
                row["review_count"] = int(cf.group(1).replace(".", ""))
        img_m = _IMAGE_RE.search(card)
        if img_m:
            row["image"] = img_m.group(0)
        camp_m = _CAMPAIGN_RE.search(card)
        if camp_m:
            row["campaign"] = _clean(camp_m.group(1))
        var_m = _VARIANTS_RE.search(card)
        if var_m:
            row["variants_count"] = int(var_m.group(1))
        out.append(row)
        if len(out) >= limit:
            break
    return out


def price_stats(products: list[dict]) -> dict:
    prices = sorted(p["price_try"] for p in products if p.get("price_try") is not None)
    if not prices:
        return {"count": 0}
    return {
        "count": len(prices),
        "min_try": prices[0],
        "median_try": round(statistics.median(prices), 2),
        "mean_try": round(sum(prices) / len(prices), 2),
        "max_try": prices[-1],
    }


# ---------------------------------------------------------------- detail

_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S
)


def _walk(obj):
    """Yield every dict inside a parsed JSON-LD document."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _ldjson_docs(html: str) -> list:
    docs = []
    for m in _LDJSON_RE.finditer(html):
        try:
            docs.append(json.loads(m.group(1)))
        except (json.JSONDecodeError, ValueError):
            continue
    return docs


def _find_product(html: str) -> dict | None:
    for doc in _ldjson_docs(html):
        for node in _walk(doc):
            if node.get("@type") == "Product":
                return node
    return None


def parse_product_detail(html: str) -> dict:
    product = _find_product(html)
    if not product:
        raise ValueError("no schema.org Product data found on this page")
    offers = product.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    rating = product.get("aggregateRating") or {}
    brand = product.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    price = offers.get("price")
    try:
        price_try = float(price) if price is not None else None
    except (TypeError, ValueError):
        price_try = None
    availability = str(offers.get("availability") or "")
    detail: dict = {
        "name": product.get("name"),
        "sku": product.get("sku"),
        "brand": brand,
        "category": product.get("category"),
        "color": product.get("color"),
        "gtin": product.get("gtin"),
        "description": product.get("description"),
        "price_try": price_try,
        "price_currency": offers.get("priceCurrency") or "TRY",
        "in_stock": ("InStock" in availability) if availability else None,
        "rating": (
            float(rating.get("ratingValue"))
            if rating.get("ratingValue") is not None
            else None
        ),
        "review_count": (
            int(str(rating.get("ratingCount") or rating.get("reviewCount") or 0).replace(".", ""))
            if (rating.get("ratingCount") or rating.get("reviewCount")) is not None
            else None
        ),
        "images": (product.get("image") or [])[:5],
        "url": offers.get("url"),
    }
    # Seller block: "Satıcı: <a href="/magaza/…">Name</a>" + "Resmi Satıcı" badge.
    seller_m = re.search(
        r"Satıcı:\s*</span><a[^>]*href=\"([^\"]+)\"[^>]*><span[^>]*>([^<]+)</span>",
        html,
    )
    if seller_m:
        detail["seller"] = _html.unescape(seller_m.group(2)).strip()
        href = seller_m.group(1)
        detail["seller_url"] = href if href.startswith("http") else BASE + href
        region = html[seller_m.start():seller_m.start() + 1500]
        detail["official_seller"] = "Resmi Satıcı" in region
    # Highlights: "Ürün Özellikleri" <ul> bullets.
    hl_m = re.search(r"Ürün Özellikleri</h2>(.*?)</ul>", html, re.S)
    if hl_m:
        items = []
        for li in re.findall(r"<li>(.*?)</li>", hl_m.group(1), re.S):
            text = _clean(li).lstrip("✅✔️• ").strip()
            if text:
                items.append(text)
        if items:
            detail["highlights"] = items
    title_m = re.search(r"<title>\s*([^<]+?)\s*</title>", html)
    if title_m and not detail.get("name"):
        detail["name"] = _clean(title_m.group(1))
    return {k: v for k, v in detail.items() if v is not None}


def parse_reviews(html: str, limit: int = 5) -> list[dict]:
    out: list[dict] = []
    for doc in _ldjson_docs(html):
        for node in _walk(doc):
            if node.get("@type") == "Review":
                author = node.get("author")
                if isinstance(author, dict):
                    author = author.get("name")
                rr = node.get("reviewRating") or {}
                out.append(
                    {
                        "author": author,
                        "rating": (
                            float(rr.get("ratingValue"))
                            if rr.get("ratingValue") is not None
                            else None
                        ),
                        "body": node.get("reviewBody"),
                        "date": node.get("datePublished"),
                    }
                )
                if len(out) >= limit:
                    return out
    return out


# ---------------------------------------------------------------- categories

_CAT_RE = re.compile(
    r'<a[^>]*href="(/[^"]*-c-(\d+))"[^>]*>(.*?)</a>', re.S
)


def parse_categories(html: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for m in _CAT_RE.finditer(html):
        path, cat_id, inner = m.group(1), m.group(2), m.group(3)
        name = _clean(inner)
        if not name or len(name) > 60 or path in seen:
            continue
        seen.add(path)
        out.append(
            {"name": name, "url": BASE + path, "category_id": cat_id}
        )
    return out
