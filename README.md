# hepsiburada-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/hepsiburada-mcp

Unofficial MCP server for **hepsiburada.com**, Türkiye's leading e-commerce marketplace — search millions of products, read product details (price, stock, seller, GTIN, highlights), read customer reviews, browse the 9 top categories, and get price statistics (min / median / mean / max) for any query. Read-only tools need no login. Optional **account actions** (cart + favorites) use your own browser session, stored only in your MCP config — see [Account actions](#account-actions).

> Built by Mohammad Abbasi as part of the "Turkey MCP factory" (Sepehr-style pipeline). Not affiliated with hepsiburada.com.

## For AI agents

Add to your MCP client config (stdio):

```json
{
  "mcpServers": {
    "hepsiburada": {
      "command": "uvx",
      "args": ["hepsiburada-mcp==0.2.0"]
    }
  }
}
```

Or run locally: `python -m hepsiburada_mcp.server` (needs `mcp<2`, `curl-cffi`).

For account actions (cart + favorites), add your browser session cookie
to the config — see [Account actions](#account-actions):

```json
{
  "mcpServers": {
    "hepsiburada": {
      "command": "uvx",
      "args": ["hepsiburada-mcp==0.2.0"],
      "env": {
        "HEPSIBURADA_SESSION": "YOUR_SESSION_COOKIE_HERE"
      }
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `hepsiburada_search` | Search products by keyword — `query` ("iphone", "kablosuz kulaklık"), `sort` ("relevance" / "price_asc" / "price_desc"), `limit` 1..24, `page` 1-based; returns title, price in TRY, rating, review count, URL, SKU, image, campaign |
| `hepsiburada_product_detail` | Detail of one product (`product` = full URL or path with "-p-HBCV…"): name, brand, price in TRY, stock status, rating, review count, seller (+ official-seller flag), category path, color, GTIN, images, highlights, plus `listing_id` / `product_id` / `merchant_id` (for account actions) |
| `hepsiburada_list_categories` | The 9 top categories: Turkish name, URL, category id |
| `hepsiburada_price_stats` | Price statistics for a query: count, min / median / mean / max price in TRY across the first page |
| `hepsiburada_product_reviews` | Recent customer reviews of one product: author, star rating, review text, date |
| `hepsiburada_view_cart` | Your cart: items (basket item id, SKU, name, quantity, price in TRY, selected / buy-later), total item count and total price, plus a cart URL — needs `HEPSIBURADA_SESSION` |
| `hepsiburada_add_to_cart` | Add a product to your cart (`sku`, `listing_id` or `product_url`, `quantity` 1..99) — needs session + `confirm=true` |
| `hepsiburada_remove_from_cart` | Remove one item from your cart (`basket_item_id` GUID from `hepsiburada_view_cart`, `basket_type` "Primary" / "Secondary") — needs session + `confirm=true` |
| `hepsiburada_update_cart_quantity` | Change one cart item's quantity (`basket_item_id`, `quantity` 1..99) — needs session + `confirm=true` |
| `hepsiburada_list_favorites` | Your favorite product SKUs — needs `HEPSIBURADA_SESSION` |
| `hepsiburada_add_favorite` | Add a product to your favorites (`sku`, `listing_id` + `product_id` or `product_url`) — needs session + `confirm=true` |
| `hepsiburada_remove_favorite` | Remove a product from your favorites (`sku`) — needs session + `confirm=true` |

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

## Account actions

Cart and favorites tools work with **your own browser session** — no
password, no API key, no account is created anywhere. The session lives
only in your MCP client config on your own machine and is sent only to
hepsiburada.com. The server never logs, prints, or persists it, and it
never appears in any tool output. Every mutation (add / remove /
change quantity) also needs `confirm=true`, or it does nothing.

### Setup (one time)

1. Log in to [hepsiburada.com](https://www.hepsiburada.com) in your
   browser (Chrome / Edge / Firefox).
2. Open DevTools (F12) → **Network** tab → reload the page.
3. Click any request to `hepsiburada.com` → **Headers** → find the
   **Cookie** request header → copy its full value.
   (Alternative: DevTools → **Application** → **Cookies** →
   `https://www.hepsiburada.com` — but the Network-tab Cookie header is
   the complete value; copy that one.)
4. Paste it as `HEPSIBURADA_SESSION` in your MCP client config (see
   the example above) and restart the MCP server.
5. Try `hepsiburada_view_cart` — it should show your real cart.

### Notes

- The session expires: when a tool reports "session expired", repeat
  steps 2–4 to copy fresh cookies. Logging out of hepsiburada.com
  revokes the session immediately.
- **Never share the cookie value** — anyone holding it has full access
  to your Hepsiburada account (cart, favorites, orders). Do not paste
  it into chats, issues, or screenshots.
- Account actions are deliberately narrow: cart (view / add / remove /
  change quantity) and favorites (list / add / remove). There is no
  checkout, payment, coupon, or bulk action.
- `listing_id` / `product_id` come from `hepsiburada_product_detail`,
  or pass `product_url` to the add tools and they are resolved from
  the product page automatically.

## How it works

hepsiburada.com returns HTTP 403 to plain HTTP clients, so the transport
uses Chrome TLS impersonation (`curl-cffi`, `chrome120`). There is no public
JSON API — data comes from the site's server-rendered HTML: search pages
carry product cards, product pages carry schema.org Product JSON-LD plus a
seller block and a "Ürün Özellikleri" highlights list, and the homepage
carries the top categories. Requests are spaced ~0.8s apart; read-only
tools need no login and no API key. Account tools call Hepsiburada's own
checkout / basket / favorites APIs with your browser session (see
[Account actions](#account-actions)); the endpoints were verified live
(each returns HTTP 401 without a session, proving the path + auth gate).

## Install

```bash
uvx hepsiburada-mcp==0.2.0        # run directly (needs uv)
# or
pip install hepsiburada-mcp==0.2.0
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
