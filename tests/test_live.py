"""Live tests for hepsiburada_mcp — real requests to hepsiburada.com.

Requires network + Chrome TLS impersonation (curl-cffi). The server is
polite by design (~0.8s between requests), so this file takes ~10s.
Run: python -m unittest discover -s tests -v
"""
import json
import unittest

from hepsiburada_mcp import account as A
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


class TestLiveAccountProbes(unittest.TestCase):
    """Unauthenticated probes of the account endpoints (no session).

    Every authed endpoint must answer HTTP 401 {"Message":"Invalid
    Token"} without a session, proving the path + auth gate; the XSRF
    endpoint answers 200. Nothing here can mutate an account — the
    calls carry no session at all. Network errors skip (transient),
    they do not fail.
    """

    FAKE_GUID = "00000000-0000-4000-8000-000000000000"

    def _probe(self, method, url, headers=None, body=None):
        try:
            return A._raw_request(method, url, headers or {}, body)
        except A.AccountError as e:
            raise unittest.SkipTest(f"network unavailable: {e}")

    def _assert_401(self, method, url, headers=None, body=None):
        resp = self._probe(method, url, headers, body)
        self.assertEqual(resp.status_code, 401, f"{method} {url}")
        self.assertEqual(resp.json().get("Message"), "Invalid Token")

    def test_basket_all_401(self):
        self._assert_401(
            "GET", f"{A.BASKET_WEB_API}/basket/all",
            {"Accept": "application/json"},
        )

    def test_add_to_cart_401(self):
        self._assert_401(
            "PUT", f"{A.CHECKOUT_API}/basket",
            {"Accept": "application/json",
             "Content-Type": "application/json; charset=utf-8",
             "tenant-id": A.TENANT_ID, "client-id": A.CLIENT_ID},
            {"product": {"metadata": {"sku": "HBCV00004X9ZCK",
                                      "listingId": self.FAKE_GUID},
                         "quantity": 1, "origin": "SfProductDetail"}},
        )

    def test_remove_from_cart_401(self):
        self._assert_401(
            "DELETE",
            f"{A.BASKET_WEB_API}/basket/item/{self.FAKE_GUID}",
            {"Accept": "application/json", "basket-type": "Primary"},
        )

    def test_update_cart_quantity_401(self):
        self._assert_401(
            "PATCH",
            f"{A.BASKET_WEB_API}/basket/item/{self.FAKE_GUID}",
            {"Accept": "application/json",
             "Content-Type": "application/json", "basket-type": "Primary"},
            [{"value": 2, "path": "/Quantity", "op": "replace",
              "from": "int"}],
        )

    def test_list_favorites_401(self):
        self._assert_401(
            "GET", f"{A.FAVORITES_API}/favorite-skus",
            {"Accept": "application/json"},
        )

    def test_add_favorite_401(self):
        self._assert_401(
            "POST", f"{A.FAVORITES_API}/favorites",
            {"Accept": "application/json",
             "Content-Type": "application/json"},
            {"sku": "HBCV00004X9ZCK", "listingId": self.FAKE_GUID,
             "productId": "HBC00004X9ZCG"},
        )

    def test_remove_favorite_401(self):
        self._assert_401(
            "DELETE", f"{A.FAVORITES_API}/favorites/HBCV00004X9ZCK",
            {"Accept": "application/json"},
        )

    def test_xsrf_token_200(self):
        resp = self._probe(
            "GET", f"{A.OAUTH_API}/xsrf-token",
            {"Accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("xsrfToken"))


if __name__ == "__main__":
    unittest.main()
