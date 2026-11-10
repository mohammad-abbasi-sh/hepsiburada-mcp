"""Offline tests for hepsiburada_mcp.products — recorded real pages.

Fixtures are trimmed excerpts of real hepsiburada.com pages fetched
2026-11-06 (search "iphone", iPhone 15 product page, homepage).
"""
import asyncio
import os
import unittest

from hepsiburada_mcp import products as P

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name: str) -> str:
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class TestTrNumbers(unittest.TestCase):
    def test_price_formats(self):
        self.assertEqual(P.parse_tr_number("56.999"), 56999.0)
        self.assertEqual(P.parse_tr_number("56.999,00"), 56999.0)
        self.assertEqual(P.parse_tr_number("1.234,56"), 1234.56)
        self.assertEqual(P.parse_tr_number("4,8"), 4.8)
        self.assertEqual(P.parse_tr_number("599"), 599.0)

    def test_bad_number(self):
        with self.assertRaises(ValueError):
            P.parse_tr_number("abc")


class TestSearchParse(unittest.TestCase):
    def setUp(self):
        self.html = _read("search-iphone.html")

    def test_three_products(self):
        rows = P.parse_search_results(self.html, limit=10)
        self.assertEqual(len(rows), 3)
        first = rows[0]
        self.assertEqual(first["title"], "Apple iPhone 15 128 GB Mavi")
        self.assertEqual(first["sku"], "HBCV00004X9ZCK")
        self.assertEqual(
            first["url"],
            "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK",
        )
        self.assertEqual(first["price_try"], 56999.0)
        self.assertEqual(first["rating"], 4.8)
        self.assertEqual(first["review_count"], 13102)
        self.assertTrue(first["image"].startswith("https://productimages.hepsiburada.net/"))

    def test_second_and_third(self):
        rows = P.parse_search_results(self.html, limit=10)
        self.assertEqual(rows[1]["title"], "Apple iPhone 17 Pro 256 GB Kozmik Turuncu")
        self.assertEqual(rows[1]["price_try"], 102999.0)
        self.assertEqual(rows[1]["rating"], 4.6)
        self.assertEqual(rows[1]["review_count"], 1535)
        self.assertEqual(rows[2]["price_try"], 113349.0)
        self.assertEqual(rows[2]["review_count"], 2149)

    def test_limit(self):
        self.assertEqual(len(P.parse_search_results(self.html, limit=2)), 2)

    def test_empty_html(self):
        self.assertEqual(P.parse_search_results("<html></html>"), [])

    def test_price_stats(self):
        rows = P.parse_search_results(self.html, limit=10)
        stats = P.price_stats(rows)
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["min_try"], 56999.0)
        self.assertEqual(stats["median_try"], 102999.0)
        self.assertEqual(stats["mean_try"], 91115.67)
        self.assertEqual(stats["max_try"], 113349.0)

    def test_price_stats_empty(self):
        self.assertEqual(P.price_stats([]), {"count": 0})


class TestDetailParse(unittest.TestCase):
    def setUp(self):
        self.html = _read("product-iphone15.html")

    def test_core_fields(self):
        d = P.parse_product_detail(self.html)
        self.assertEqual(d["name"], "Apple iPhone 15 128 GB")
        self.assertEqual(d["sku"], "HBCV00004X9ZCK")
        self.assertEqual(d["brand"], "Apple")
        self.assertEqual(d["category"], "Telefon > Cep Telefonu > iPhone iOS Telefonlar")
        self.assertEqual(d["color"], "Mavi")
        self.assertEqual(d["gtin"], "0195949036583")
        self.assertEqual(d["price_try"], 56999.0)
        self.assertEqual(d["price_currency"], "TRY")
        self.assertTrue(d["in_stock"])
        self.assertEqual(d["rating"], 4.8)
        self.assertEqual(d["review_count"], 13102)

    def test_seller(self):
        d = P.parse_product_detail(self.html)
        self.assertEqual(d["seller"], "Hepsiburada")
        self.assertEqual(d["seller_url"], "https://www.hepsiburada.com/magaza/hepsiburada")
        self.assertTrue(d["official_seller"])

    def test_highlights_and_images(self):
        d = P.parse_product_detail(self.html)
        self.assertEqual(len(d["highlights"]), 5)
        self.assertTrue(d["highlights"][0].startswith("Ekran"))
        self.assertEqual(len(d["images"]), 5)
        self.assertTrue(d["images"][0].startswith("https://productimages.hepsiburada.net/"))

    def test_no_product_raises(self):
        with self.assertRaises(ValueError):
            P.parse_product_detail("<html><body>no json-ld here</body></html>")


class TestReviewsParse(unittest.TestCase):
    def test_reviews(self):
        html = _read("product-iphone15.html")
        reviews = P.parse_reviews(html, limit=5)
        self.assertGreaterEqual(len(reviews), 1)
        first = reviews[0]
        self.assertEqual(first["author"], "Abdullah Emin E***")
        self.assertEqual(first["rating"], 5.0)
        self.assertIn("memnunum", first["body"])
        self.assertEqual(first["date"], "2023-09-25")

    def test_limit(self):
        html = _read("product-iphone15.html")
        self.assertEqual(len(P.parse_reviews(html, limit=1)), 1)

    def test_no_reviews(self):
        self.assertEqual(P.parse_reviews("<html></html>"), [])


class TestCategoriesParse(unittest.TestCase):
    def test_nine_categories(self):
        cats = P.parse_categories(_read("home-categories.html"))
        self.assertEqual(len(cats), 9)
        self.assertEqual(cats[0]["name"], "Elektronik")
        self.assertEqual(
            cats[0]["url"],
            "https://www.hepsiburada.com/ev-elektronik-urunleri-c-2147483638",
        )
        self.assertEqual(cats[0]["category_id"], "2147483638")
        self.assertEqual(cats[-1]["name"], "Kitap, Müzik, Film, Hobi")

    def test_empty(self):
        self.assertEqual(P.parse_categories("<html></html>"), [])


class TestSorts(unittest.TestCase):
    def test_resolve(self):
        self.assertIsNone(P.resolve_sort("relevance"))
        self.assertEqual(P.resolve_sort("price_asc"), "artanfiyat")
        self.assertEqual(P.resolve_sort("price_desc"), "azalanfiyat")

    def test_unknown_sort(self):
        with self.assertRaises(ValueError):
            P.resolve_sort("bogus")


class TestServerToolsRegistered(unittest.TestCase):
    def test_tools_registered(self):
        from hepsiburada_mcp.server import mcp

        tools = asyncio.run(mcp.list_tools())
        names = sorted(t.name for t in tools)
        self.assertEqual(
            names,
            [
                "hepsiburada_health",
                "hepsiburada_list_categories",
                "hepsiburada_price_stats",
                "hepsiburada_product_detail",
                "hepsiburada_product_reviews",
                "hepsiburada_search",
            ],
        )


if __name__ == "__main__":
    unittest.main()
