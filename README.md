# hepsiburada-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/hepsiburada-mcp

Unofficial **read-only** MCP server for **hepsiburada.com**, Türkiye's leading e-commerce marketplace — search millions of products, read product details (price, stock, seller, GTIN, highlights), read customer reviews, browse the 9 top categories, and get price statistics (min / median / mean / max) for any query.

> Built by Mohammad Abbasi as part of the "Turkey MCP factory" (Sepehr-style pipeline). Not affiliated with hepsiburada.com.

## For AI agents

Add to your MCP client config (stdio):

```json
{
  "mcpServers": {
    "hepsiburada": {
      "command": "uvx",
      "args": ["hepsiburada-mcp==0.1.1"]
    }
  }
}
```

Or run locally: `python -m hepsiburada_mcp.server` (needs `mcp<2`, `curl-cffi`).

## Tools

| Tool | Description |
|------|-------------|
| `hepsiburada_search` | Search products by keyword — `query` ("iphone", "kablosuz kulaklık"), `sort` ("relevance" / "price_asc" / "price_desc"), `limit` 1..24, `page` 1-based; returns title, price in TRY, rating, review count, URL, SKU, image, campaign |
| `hepsiburada_product_detail` | Detail of one product (`product` = full URL or path with "-p-HBCV…"): name, brand, price in TRY, stock status, rating, review count, seller (+ official-seller flag), category path, color, GTIN, images, highlights |
| `hepsiburada_list_categories` | The 9 top categories: Turkish name, URL, category id |
| `hepsiburada_price_stats` | Price statistics for a query: count, min / median / mean / max price in TRY across the first page |
| `hepsiburada_product_reviews` | Recent customer reviews of one product: author, star rating, review text, date |

Example output (`hepsiburada_search` / "iphone"):

```json
{"query": "iphone", "sort": "relevance", "page": 1, "count": 3, "products": [
  {"title": "Apple iPhone 15 128 GB Mavi",
   "url": "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK",
   "sku": "HBCV00004X9ZCK", "price_try": 56999.0, "rating": 4.8,
   "review_count": 13102, "campaign": "30 günün en düşük fiyatı"}, …]}
```

Example output (`hepsiburada_product_detail` / iPhone 15):

```json
{"name": "Apple iPhone 15 128 GB", "sku": "HBCV00004X9ZCK", "brand": "Apple",
 "category": "Telefon > Cep Telefonu > iPhone iOS Telefonlar", "color": "Mavi",
 "gtin": "0195949036583", "price_try": 56999.0, "price_currency": "TRY",
 "in_stock": true, "rating": 4.8, "review_count": 13102,
 "seller": "Hepsiburada", "official_seller": true,
 "highlights": ["Ekran : 6.1 inç Super Retina XDR OLED, …"], …}
```

Example output (`hepsiburada_price_stats` / "iphone"):

```json
{"query": "iphone", "sort": "relevance", "count": 3, "min_try": 56999.0,
 "median_try": 102999.0, "mean_try": 91115.67, "max_try": 113349.0}
```

## How it works

hepsiburada.com returns HTTP 403 to plain HTTP clients, so the transport
uses Chrome TLS impersonation (`curl-cffi`, `chrome120`). There is no public
JSON API — data comes from the site's server-rendered HTML: search pages
carry product cards, product pages carry schema.org Product JSON-LD plus a
seller block and a "Ürün Özellikleri" highlights list, and the homepage
carries the top categories. Requests are spaced ~0.8s apart; everything is
read-only, no login, no API key.

## Install

```bash
uvx hepsiburada-mcp==0.1.1        # run directly (needs uv)
# or
pip install hepsiburada-mcp==0.1.1
hepsiburada-mcp            # starts the MCP server on stdio
```

## Tests

```bash
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

Offline tests run on recorded fixtures (real pages fetched 2026-11-06);
live tests hit hepsiburada.com.

## Roadmap

- Category-scoped search (search within one `-c-…` category)
- Seller store pages (other sellers of the same product)
- Price history (track a SKU over days)

## License

MIT — see [LICENSE](LICENSE).

---

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
