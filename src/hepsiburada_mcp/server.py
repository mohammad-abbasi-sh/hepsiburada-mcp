"""MCP server: unofficial read-only access to hepsiburada.com shopping."""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from . import http as _http
from . import products as _P

mcp = FastMCP("hepsiburada-mcp")

INSTRUCTIONS = """\
Unofficial read-only MCP server for hepsiburada.com, Türkiye's leading
e-commerce marketplace. Data comes from the site's public server-rendered
pages: search pages carry product cards (title, final price in TRY,
rating, review count, campaign text), product pages carry schema.org
Product JSON-LD (price, availability, brand, GTIN, images) plus a seller
block and a "Ürün Özellikleri" highlights list, and the homepage carries
the 9 top categories. Product URLs look like
"/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK" (the HBCV… code is the
SKU; use hepsiburada_search to find product URLs). Prices are in Turkish
Lira (TRY) unless noted. Read-only, no login, no API key. Transport uses
Chrome TLS impersonation because the site 403s plain HTTP clients; the
server spaces requests ~0.8s apart. Built by Mohammad Abbasi
(mohammad-abbasi-sh) — Turkey MCP factory.\
"""


def _err(e: Exception) -> str:
    return json.dumps({"error": str(e)}, ensure_ascii=False)


def _validate_limit(limit: int) -> int:
    if not 1 <= limit <= 24:
        raise ValueError("limit must be between 1 and 24")
    return limit


@mcp.tool()
def hepsiburada_search(query: str, limit: int = 10, sort: str = "relevance", page: int = 1) -> str:
    """Search hepsiburada.com products by keyword. query: Turkish or ASCII,
    e.g. "iphone", "kablosuz kulaklık", "laptop". sort: "relevance" (default),
    "price_asc" (cheapest first), "price_desc" (most expensive first).
    limit 1..24; page 1-based. Returns title, price in TRY, rating,
    review count, product URL, SKU, image and campaign text per product."""
    try:
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        _validate_limit(limit)
        if page < 1:
            raise ValueError("page must be >= 1")
        sort_param = _P.resolve_sort(sort)
        html = _http.fetch_search_html(query.strip(), sort_param=sort_param, page=page)
        rows = _P.parse_search_results(html, limit=limit)
    except (ValueError, _http.HepsiburadaError) as e:
        return _err(e)
    return json.dumps(
        {"query": query.strip(), "sort": sort, "page": page,
         "count": len(rows), "products": rows},
        ensure_ascii=False,
    )


@mcp.tool()
def hepsiburada_product_detail(product: str) -> str:
    """Detail of one product: name, brand, price in TRY, stock status,
    rating and review count, seller (+ official-seller flag), category path,
    color, GTIN, images, highlights. product: a full product URL or site
    path containing "-p-HBCV…" (find one with hepsiburada_search first),
    e.g. "/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK"."""
    try:
        html = _http.fetch_product_html(product)
        detail = _P.parse_product_detail(html)
    except (ValueError, _http.HepsiburadaError) as e:
        return _err(e)
    return json.dumps(detail, ensure_ascii=False)


@mcp.tool()
def hepsiburada_list_categories() -> str:
    """Top categories of hepsiburada.com (9 main categories): Turkish name,
    category URL and category id. Use a category URL with hepsiburada_search
    via the query, or browse it in a browser."""
    try:
        html = _http.fetch_home_html()
        cats = _P.parse_categories(html)
    except _http.HepsiburadaError as e:
        return _err(e)
    return json.dumps({"count": len(cats), "categories": cats}, ensure_ascii=False)


@mcp.tool()
def hepsiburada_price_stats(query: str, limit: int = 24, sort: str = "relevance") -> str:
    """Price statistics for a search query: product count, min / median /
    mean / max price in TRY across the first page of results.
    query: e.g. "iphone 15"; limit 1..24 (default 24 = whole first page)."""
    try:
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        _validate_limit(limit)
        sort_param = _P.resolve_sort(sort)
        html = _http.fetch_search_html(query.strip(), sort_param=sort_param)
        rows = _P.parse_search_results(html, limit=limit)
        stats = _P.price_stats(rows)
    except (ValueError, _http.HepsiburadaError) as e:
        return _err(e)
    return json.dumps(
        {"query": query.strip(), "sort": sort, **stats}, ensure_ascii=False
    )


@mcp.tool()
def hepsiburada_product_reviews(product: str, limit: int = 5) -> str:
    """Recent customer reviews of one product: author, star rating, review
    text and date. product: a full product URL or site path containing
    "-p-HBCV…" (find one with hepsiburada_search first). limit 1..24."""
    try:
        _validate_limit(limit)
        html = _http.fetch_product_html(product)
        reviews = _P.parse_reviews(html, limit=limit)
    except (ValueError, _http.HepsiburadaError) as e:
        return _err(e)
    return json.dumps(
        {"product": product, "count": len(reviews), "reviews": reviews},
        ensure_ascii=False,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
