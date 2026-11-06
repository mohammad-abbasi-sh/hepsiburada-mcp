"""Live tests for hepsiburada_mcp — real requests to hepsiburada.com.

Requires network + Chrome TLS impersonation (curl-cffi). The server is
polite by design (~0.8s between requests), so this file takes ~10s.
Run: python -m unittest discover -s tests -v
"""
import json
import unittest

from hepsiburada_mcp import http as H
from hepsiburada_mcp import products as P

KNOWN_PRODUCT = "/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK"


class TestLiveSearch(unittest.TestCase):
    def test_search_iphone(self):
        html = H.fetch_search_html("iphone")
        rows = P.parse_search_results(html, limit=3)
        self.assertGreaterEqual(len(rows), 1)
        first = rows[0]
        self.assertTrue(first["title"])
        self.assertTrue(first["price_try"] > 0)
        self.assertTrue(first["sku"].startswith("HBCV"))
        self.assertTrue(first["url"].startswith("https://www.hepsiburada.com/"))

    def test_search_price_desc_order(self):
        html = H.fetch_search_html("iphone", sort_param="azalanfiyat")
        rows = P.parse_search_results(html, limit=10)
        self.assertGreaterEqual(len(rows), 2)
        prices = [r["price_try"] for r in rows]
        self.assertGreaterEqual(prices[0], prices[-1])

    def test_search_no_results_shape(self):
        # A nonsense query returns a page; parser must not crash.
        html = H.fetch_search_html("zzzxqqqwwwnonexistent")
        rows = P.parse_search_results(html, limit=5)
        self.assertIsInstance(rows, list)


class TestLiveDetail(unittest.TestCase):
    def test_known_product(self):
        html = H.fetch_product_html(KNOWN_PRODUCT)
        d = P.parse_product_detail(html)
        self.assertIn("iPhone 15", d["name"])
        self.assertEqual(d["sku"], "HBCV00004X9ZCK")
        self.assertTrue(d["price_try"] > 0)
        self.assertEqual(d["price_currency"], "TRY")
        self.assertEqual(d["seller"], "Hepsiburada")

    def test_known_product_reviews(self):
        html = H.fetch_product_html(KNOWN_PRODUCT)
        reviews = P.parse_reviews(html, limit=3)
        self.assertGreaterEqual(len(reviews), 1)
        self.assertIsNotNone(reviews[0]["rating"])

    def test_bad_product_path(self):
        with self.assertRaises(H.HepsiburadaError):
            H.fetch_product_html("not-a-product-path")


class TestLiveCategoriesAndStats(unittest.TestCase):
    def test_categories(self):
        cats = P.parse_categories(H.fetch_home_html())
        self.assertGreaterEqual(len(cats), 5)
        names = [c["name"] for c in cats]
        self.assertIn("Elektronik", names)

    def test_price_stats(self):
        html = H.fetch_search_html("iphone")
        rows = P.parse_search_results(html, limit=10)
        stats = P.price_stats(rows)
        self.assertGreaterEqual(stats["count"], 1)
        self.assertLessEqual(stats["min_try"], stats["median_try"])
        self.assertLessEqual(stats["median_try"], stats["max_try"])


class TestLiveToolsEndToEnd(unittest.TestCase):
    """Exercise the MCP tool functions themselves (they hit the network)."""

    def test_search_tool_json(self):
        from hepsiburada_mcp.server import hepsiburada_search

        out = json.loads(hepsiburada_search("iphone", limit=2))
        self.assertEqual(out["query"], "iphone")
        self.assertEqual(out["count"], 2)
        self.assertTrue(out["products"][0]["price_try"] > 0)

    def test_stats_tool_json(self):
        from hepsiburada_mcp.server import hepsiburada_price_stats

        out = json.loads(hepsiburada_price_stats("iphone", limit=5))
        self.assertGreaterEqual(out["count"], 1)
        self.assertLessEqual(out["min_try"], out["max_try"])

    def test_bad_sort_tool_error_json(self):
        from hepsiburada_mcp.server import hepsiburada_search

        out = json.loads(hepsiburada_search("iphone", sort="nope"))
        self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
