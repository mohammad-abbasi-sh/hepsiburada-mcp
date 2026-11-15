"""Offline tests for hepsiburada_mcp.account — local-session cart + favorites.

All HTTP is mocked (account._raw_request patched); no network calls and
no real session material anywhere. Fake cookie values are obvious
placeholders ("fake-jwt-token", ...). Fixtures: the recorded 401 body
(account-401.json, captured live 2026-11-15) plus SYNTHETIC success
responses shaped per the public JS findings (the real authed response
shapes are unverified without a live account — parsers are defensive).
"""
import json
import os
import unittest
from unittest import mock

from hepsiburada_mcp import account as A
from hepsiburada_mcp import products as P

FIX = os.path.join(os.path.dirname(__file__), "fixtures")

FAKE_SESSION = (
    "jwt=fake-jwt-token; hpJwtToken=fake-hp-jwt-token; "
    "hbus_anonymousId=fake-anon-id; uniqueDeviceId=fake-device-id; "
    "location=fake-location"
)
FAKE_LISTING = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
FAKE_PRODUCT = "HBC00004X9ZCG"
FAKE_SKU = "HBCV00004X9ZCK"
FAKE_ITEM = "11111111-1111-4111-8111-111111111111"


def _read(name: str) -> str:
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


def _read_json(name: str):
    return json.loads(_read(name))


class FakeHeaders(dict):
    def get_list(self, name):
        value = self.get(name.lower())
        if isinstance(value, list):
            return value
        return [value] if value else []


class FakeResponse:
    def __init__(self, status_code, body=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = FakeHeaders(headers or {})

    @property
    def text(self):
        if self._body is None:
            return ""
        if isinstance(self._body, str):
            return self._body
        return json.dumps(self._body)

    def json(self):
        return self._body


class AccountTestCase(unittest.TestCase):
    def setUp(self):
        A._xsrf_token = None
        self.env = mock.patch.dict(
            os.environ, {A.SESSION_ENV: FAKE_SESSION}, clear=False
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.calls = []
        self.responses = {}

    def _mock_raw(self, mapping=None):
        """Patch A._raw_request; mapping: (method, url) -> FakeResponse
        (or a list of responses served in order). Records every call."""
        mapping = mapping or {}

        def fake(method, url, headers, json_body=None):
            self.calls.append((method, url, dict(headers), json_body))
            key = (method, url)
            resp = mapping.get(key)
            if isinstance(resp, list):
                return resp.pop(0) if resp else FakeResponse(500, {})
            if resp is not None:
                return resp
            return FakeResponse(404, {"Message": "not stubbed"})

        patcher = mock.patch.object(A, "_raw_request", side_effect=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake


class TestCookieParsing(AccountTestCase):
    def test_parse_cookies(self):
        session = A.Session(FAKE_SESSION)
        self.assertEqual(session.get("jwt"), "fake-jwt-token")
        self.assertEqual(session.get("hpJwtToken"), "fake-hp-jwt-token")
        self.assertEqual(session.get("hbus_anonymousId"), "fake-anon-id")
        self.assertEqual(session.get("uniqueDeviceId"), "fake-device-id")
        self.assertEqual(session.get("location"), "fake-location")
        self.assertIsNone(session.get("missing"))

    def test_parse_ignores_bare_flags(self):
        session = A.Session("jwt=fake-jwt-token; Secure; HttpOnly")
        self.assertEqual(session.get("jwt"), "fake-jwt-token")

    def test_cookie_header_roundtrip(self):
        session = A.Session(FAKE_SESSION)
        rebuilt = A._parse_cookie_header(session.cookie_header())
        self.assertEqual(rebuilt, A._parse_cookie_header(FAKE_SESSION))

    def test_refresh_adopt_overrides(self):
        session = A.Session(FAKE_SESSION)
        session.adopt("jwt", "new-fake-jwt")
        self.assertEqual(session.get("jwt"), "new-fake-jwt")
        self.assertIn("jwt=new-fake-jwt", session.cookie_header())

    def test_checkout_headers(self):
        session = A.get_session()
        headers = A._checkout_headers(session)
        self.assertEqual(headers["Authorization"], "Bearer fake-jwt-token")
        self.assertEqual(headers["tenant-id"], A.TENANT_ID)
        self.assertEqual(headers["client-id"], A.CLIENT_ID)
        self.assertEqual(headers["anonymous-user-id"], "fake-anon-id")
        self.assertEqual(headers["unique-device-id"], "fake-device-id")
        self.assertEqual(headers["location-of-customer"], "fake-location")
        self.assertIn("jwt=fake-jwt-token", headers["Cookie"])

    def test_basket_web_headers(self):
        headers = A._basket_web_headers(A.get_session())
        self.assertEqual(headers["HPBearer"], "fake-hp-jwt-token")
        self.assertEqual(headers["anonymous-user-id"], "fake-anon-id")

    def test_headers_omit_missing_cookies(self):
        session = A.Session("jwt=only-jwt")
        headers = A._checkout_headers(session)
        self.assertEqual(headers["Authorization"], "Bearer only-jwt")
        self.assertNotIn("anonymous-user-id", headers)
        self.assertNotIn("unique-device-id", headers)
        self.assertNotIn("HPBearer", A._basket_web_headers(session))

    def test_get_session_reads_env_at_call_time(self):
        with mock.patch.dict(os.environ, {A.SESSION_ENV: "jwt=second-fake"}):
            self.assertEqual(A.get_session().get("jwt"), "second-fake")
        self.assertEqual(A.get_session().get("jwt"), "fake-jwt-token")


class TestNoSession(unittest.TestCase):
    def setUp(self):
        A._xsrf_token = None
        self.env = mock.patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def _assert_inert(self, fn, *args, **kwargs):
        with mock.patch.object(
            A, "_raw_request", side_effect=AssertionError("network call made")
        ):
            with self.assertRaises(A.SessionNotConfigured) as ctx:
                fn(*args, **kwargs)
        self.assertIn("HEPSIBURADA_SESSION is not configured", str(ctx.exception))
        # The error must not leak any session material (there is none).
        self.assertNotIn("fake-jwt", str(ctx.exception))

    def test_all_account_tools_inert_without_session(self):
        self._assert_inert(A.view_cart)
        self._assert_inert(A.add_to_cart, FAKE_SKU, listing_id=FAKE_LISTING)
        self._assert_inert(A.remove_from_cart, FAKE_ITEM)
        self._assert_inert(A.update_cart_quantity, FAKE_ITEM, 2)
        self._assert_inert(A.list_favorites)
        self._assert_inert(
            A.add_favorite, FAKE_SKU, listing_id=FAKE_LISTING,
            product_id=FAKE_PRODUCT,
        )
        self._assert_inert(A.remove_favorite, FAKE_SKU)

    def test_add_to_cart_with_url_makes_no_fetch_without_session(self):
        # Even the public product-page fetch must not happen: no network
        # at all when the session is missing.
        with mock.patch.object(
            A, "_raw_request", side_effect=AssertionError("network call made")
        ), mock.patch(
            "hepsiburada_mcp.http.fetch_product_html",
            side_effect=AssertionError("product fetch made"),
        ):
            with self.assertRaises(A.SessionNotConfigured):
                A.add_to_cart(FAKE_SKU, product_url="/x-p-HBCV00004X9ZCK")


class TestServerToolsNoSession(unittest.TestCase):
    def setUp(self):
        A._xsrf_token = None
        self.env = mock.patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_server_tools_return_error_json(self):
        from hepsiburada_mcp import server as S

        for fn in (S.hepsiburada_view_cart, S.hepsiburada_list_favorites):
            out = json.loads(fn())
            self.assertIn("HEPSIBURADA_SESSION is not configured", out["error"])
        out = json.loads(
            S.hepsiburada_add_to_cart(FAKE_SKU, listing_id=FAKE_LISTING,
                                      confirm=True)
        )
        self.assertIn("HEPSIBURADA_SESSION is not configured", out["error"])


class TestConfirmation(AccountTestCase):
    def test_mutating_tools_require_confirm(self):
        from hepsiburada_mcp import server as S

        with mock.patch.object(
            A, "_raw_request", side_effect=AssertionError("network call made")
        ):
            cases = [
                S.hepsiburada_add_to_cart(FAKE_SKU, listing_id=FAKE_LISTING),
                S.hepsiburada_remove_from_cart(FAKE_ITEM),
                S.hepsiburada_update_cart_quantity(FAKE_ITEM, 2),
                S.hepsiburada_add_favorite(
                    FAKE_SKU, listing_id=FAKE_LISTING,
                    product_id=FAKE_PRODUCT,
                ),
                S.hepsiburada_remove_favorite(FAKE_SKU),
                # Explicit confirm=False is the same as omitted.
                S.hepsiburada_remove_favorite(FAKE_SKU, confirm=False),
            ]
        for raw in cases:
            out = json.loads(raw)
            self.assertEqual(out["error"], "confirmation_required")
            self.assertIn("confirm=true", out["message"])


class TestValidation(AccountTestCase):
    def test_bad_guid(self):
        for bad in ("not-a-guid", "11111111-1111-4111-8111", "", 123):
            with self.assertRaises(ValueError, msg=bad):
                A.remove_from_cart(bad)
            with self.assertRaises(ValueError, msg=bad):
                A.update_cart_quantity(bad, 2)

    def test_quantity_bounds(self):
        for bad in (0, 100, -1, 2.5, True, "2"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                A.add_to_cart(FAKE_SKU, listing_id=FAKE_LISTING, quantity=bad)
            with self.assertRaises(ValueError, msg=repr(bad)):
                A.update_cart_quantity(FAKE_ITEM, bad)
        # But quantity 0 on update gets the specific removal hint.
        with self.assertRaises(ValueError) as ctx:
            A.update_cart_quantity(FAKE_ITEM, 0)
        self.assertIn("remove_from_cart", str(ctx.exception))

    def test_quantity_edges_ok(self):
        self._mock_raw({
            ("PUT", f"{A.CHECKOUT_API}/basket"): FakeResponse(200, {}),
        })
        A.add_to_cart(FAKE_SKU, listing_id=FAKE_LISTING, quantity=1)
        A.add_to_cart(FAKE_SKU, listing_id=FAKE_LISTING, quantity=99)

    def test_bad_basket_type(self):
        with self.assertRaises(ValueError):
            A.remove_from_cart(FAKE_ITEM, basket_type="Other")
        with self.assertRaises(ValueError):
            A.update_cart_quantity(FAKE_ITEM, 2, basket_type="primary")


class TestViewCart(AccountTestCase):
    def test_view_cart_parses_fixture(self):
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): FakeResponse(
                200, _read_json("account-basket.json")
            ),
        })
        out = A.view_cart()
        self.assertEqual(len(out["items"]), 3)
        first = out["items"][0]
        self.assertEqual(first["basket_item_id"], FAKE_ITEM)
        self.assertEqual(first["sku"], FAKE_SKU)
        self.assertEqual(first["name"], "Apple iPhone 15 128 GB Mavi")
        self.assertEqual(first["quantity"], 1)
        self.assertEqual(first["price_try"], 56999.0)
        self.assertTrue(first["is_selected"])
        self.assertEqual(first["merchant"], "Hepsiburada")
        self.assertFalse(out["items"][2]["is_selected"])
        self.assertEqual(out["total_item_count"], 4)
        self.assertEqual(out["total_price_try"], 59998.0)
        self.assertEqual(out["cart_url"], A.CART_URL)
        method, url, headers, _body = self.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(headers["HPBearer"], "fake-hp-jwt-token")

    def test_view_cart_items_key_shape(self):
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): FakeResponse(
                200, {"items": [{"id": FAKE_ITEM, "sku": FAKE_SKU,
                                "quantity": 3}]}
            ),
        })
        out = A.view_cart()
        self.assertEqual(out["items"][0]["basket_item_id"], FAKE_ITEM)
        self.assertEqual(out["total_item_count"], 3)

    def test_view_cart_unexpected_shape(self):
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): FakeResponse(
                200, {"somethingElse": 1, "other": 2}
            ),
        })
        out = A.view_cart()
        self.assertEqual(out["items"], [])
        self.assertEqual(out["note"], "unexpected response shape")
        self.assertEqual(sorted(out["response_keys"]), ["other", "somethingElse"])
        self.assertEqual(out["cart_url"], A.CART_URL)

    def test_view_cart_empty_basket_is_not_an_error(self):
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): FakeResponse(
                200, {"selectedItems": [], "unselectedItems": []}
            ),
        })
        out = A.view_cart()
        self.assertEqual(out["items"], [])
        self.assertEqual(out["total_item_count"], 0)
        self.assertNotIn("note", out)


class TestAddToCart(AccountTestCase):
    def test_add_with_listing_id(self):
        self._mock_raw({
            ("PUT", f"{A.CHECKOUT_API}/basket"): FakeResponse(
                200, _read_json("account-add-to-cart.json")
            ),
        })
        out = A.add_to_cart(FAKE_SKU, listing_id=FAKE_LISTING, quantity=2)
        self.assertTrue(out["added"])
        self.assertEqual(out["total_basket_item_count"], 3)
        method, url, headers, body = self.calls[0]
        self.assertEqual(method, "PUT")
        self.assertEqual(url, f"{A.CHECKOUT_API}/basket")
        self.assertEqual(headers["Authorization"], "Bearer fake-jwt-token")
        self.assertEqual(
            body,
            {"product": {"metadata": {"sku": FAKE_SKU,
                                      "listingId": FAKE_LISTING},
                         "quantity": 2, "origin": "SfProductDetail"}},
        )

    def test_add_resolves_listing_from_product_url(self):
        html = _read("product-listing-ids.html")
        self._mock_raw({
            ("PUT", f"{A.CHECKOUT_API}/basket"): FakeResponse(200, {}),
        })
        with mock.patch(
            "hepsiburada_mcp.http.fetch_product_html", return_value=html
        ) as fetch:
            out = A.add_to_cart(
                FAKE_SKU,
                product_url="/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK",
            )
        fetch.assert_called_once()
        self.assertTrue(out["added"])
        _m, _u, _h, body = self.calls[0]
        self.assertEqual(body["product"]["metadata"]["listingId"], FAKE_LISTING)
        self.assertEqual(
            body["product"]["metadata"]["name"], "Apple iPhone 15 128 GB"
        )
        self.assertIn("productimages.hepsiburada.net",
                      body["product"]["metadata"]["imageUrl"])

    def test_add_without_listing_or_url_errors(self):
        self._mock_raw({})
        with self.assertRaises(A.AccountError) as ctx:
            A.add_to_cart(FAKE_SKU)
        self.assertIn("listing_id is required", str(ctx.exception))
        self.assertIn("hepsiburada_product_detail", str(ctx.exception))
        self.assertEqual(self.calls, [])


class TestRemoveAndUpdateCart(AccountTestCase):
    def test_remove(self):
        self._mock_raw({
            ("DELETE", f"{A.BASKET_WEB_API}/basket/item/{FAKE_ITEM}"):
                FakeResponse(200, {}),
        })
        out = A.remove_from_cart(FAKE_ITEM)
        self.assertTrue(out["removed"])
        method, url, headers, _body = self.calls[0]
        self.assertEqual(method, "DELETE")
        self.assertEqual(headers["basket-type"], "Primary")
        self.assertEqual(headers["HPBearer"], "fake-hp-jwt-token")

    def test_remove_secondary(self):
        self._mock_raw({
            ("DELETE", f"{A.BASKET_WEB_API}/basket/item/{FAKE_ITEM}"):
                FakeResponse(204, None),
        })
        A.remove_from_cart(FAKE_ITEM, basket_type="Secondary")
        self.assertEqual(self.calls[0][2]["basket-type"], "Secondary")

    def test_update_quantity(self):
        self._mock_raw({
            ("PATCH", f"{A.BASKET_WEB_API}/basket/item/{FAKE_ITEM}"):
                FakeResponse(200, {}),
        })
        out = A.update_cart_quantity(FAKE_ITEM, 3)
        self.assertTrue(out["updated"])
        self.assertEqual(out["quantity"], 3)
        method, _url, headers, body = self.calls[0]
        self.assertEqual(method, "PATCH")
        self.assertEqual(
            body,
            [{"value": 3, "path": "/Quantity", "op": "replace",
              "from": "int"}],
        )
        self.assertEqual(headers["basket-type"], "Primary")


class TestFavorites(AccountTestCase):
    def test_list_favorites_envelope_shape(self):
        self._mock_raw({
            ("GET", f"{A.FAVORITES_API}/favorite-skus"): FakeResponse(
                200, _read_json("account-favorites.json")
            ),
        })
        out = A.list_favorites()
        self.assertEqual(out["skus"], [FAKE_SKU, "HBCV00006AAAAA"])
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["favorites_url"], A.FAVORITES_URL)

    def test_list_favorites_shapes(self):
        for body, expected in [
            (["HBCV00001AAAAA"], ["HBCV00001AAAAA"]),
            ({"skus": ["HBCV00001AAAAA"]}, ["HBCV00001AAAAA"]),
            ({"favoriteSkus": ["HBCV00001AAAAA"]}, ["HBCV00001AAAAA"]),
            ({"data": [{"sku": "HBCV00001AAAAA"}]}, ["HBCV00001AAAAA"]),
            ({"result": {"skus": ["HBCV00001AAAAA"]}}, ["HBCV00001AAAAA"]),
        ]:
            with self.subTest(body=body):
                self.calls.clear()
                self._mock_raw({
                    ("GET", f"{A.FAVORITES_API}/favorite-skus"):
                        FakeResponse(200, body),
                })
                out = A.list_favorites()
                self.assertEqual(out["skus"], expected)
                self.assertEqual(out["count"], 1)

    def test_list_favorites_unexpected_shape(self):
        self._mock_raw({
            ("GET", f"{A.FAVORITES_API}/favorite-skus"): FakeResponse(
                200, {"weird": True}
            ),
        })
        out = A.list_favorites()
        self.assertEqual(out["skus"], [])
        self.assertEqual(out["note"], "unexpected response shape")
        self.assertEqual(out["response_keys"], ["weird"])

    def _xsrf_mapping(self, extra):
        mapping = {
            ("GET", f"{A.OAUTH_API}/xsrf-token"): FakeResponse(
                200, {"xsrfToken": "fake-xsrf-token"}
            ),
        }
        mapping.update(extra)
        return mapping

    def test_add_favorite_sends_xsrf(self):
        self._mock_raw(self._xsrf_mapping({
            ("POST", f"{A.FAVORITES_API}/favorites"): FakeResponse(200, {}),
        }))
        out = A.add_favorite(
            FAKE_SKU, listing_id=FAKE_LISTING, product_id=FAKE_PRODUCT
        )
        self.assertTrue(out["added"])
        self.assertEqual(len(self.calls), 2)
        method, url, headers, body = self.calls[1]
        self.assertEqual(method, "POST")
        self.assertEqual(headers["X-XSRF-TOKEN"], "fake-xsrf-token")
        self.assertEqual(
            body,
            {"sku": FAKE_SKU, "listingId": FAKE_LISTING,
             "productId": FAKE_PRODUCT},
        )

    def test_add_favorite_resolves_from_product_url(self):
        html = _read("product-listing-ids.html")
        self._mock_raw(self._xsrf_mapping({
            ("POST", f"{A.FAVORITES_API}/favorites"): FakeResponse(200, {}),
        }))
        with mock.patch(
            "hepsiburada_mcp.http.fetch_product_html", return_value=html
        ):
            A.add_favorite(
                FAKE_SKU,
                product_url="/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK",
            )
        _m, _u, _h, body = self.calls[1]
        self.assertEqual(body["listingId"], FAKE_LISTING)
        self.assertEqual(body["productId"], FAKE_PRODUCT)

    def test_add_favorite_without_ids_errors(self):
        self._mock_raw(self._xsrf_mapping({}))
        with self.assertRaises(A.AccountError) as ctx:
            A.add_favorite(FAKE_SKU)
        self.assertIn("listing_id and product_id are required",
                      str(ctx.exception))
        self.assertEqual(self.calls, [])

    def test_remove_favorite(self):
        self._mock_raw(self._xsrf_mapping({
            ("DELETE", f"{A.FAVORITES_API}/favorites/{FAKE_SKU}"):
                FakeResponse(200, {}),
        }))
        out = A.remove_favorite(FAKE_SKU)
        self.assertTrue(out["removed"])
        method, url, headers, _body = self.calls[1]
        self.assertEqual(method, "DELETE")
        self.assertEqual(headers["X-XSRF-TOKEN"], "fake-xsrf-token")

    def test_xsrf_failure_is_an_error_not_a_guess(self):
        self._mock_raw({
            ("GET", f"{A.OAUTH_API}/xsrf-token"): FakeResponse(500, {}),
        })
        with self.assertRaises(A.AccountError) as ctx:
            A.remove_favorite(FAKE_SKU)
        self.assertIn("XSRF token", str(ctx.exception))
        self.assertEqual(len(self.calls), 1)  # no favorites call attempted

    def test_xsrf_token_cached(self):
        self._mock_raw(self._xsrf_mapping({
            ("DELETE", f"{A.FAVORITES_API}/favorites/{FAKE_SKU}"):
                FakeResponse(200, {}),
        }))
        A.remove_favorite(FAKE_SKU)
        A.remove_favorite(FAKE_SKU)
        xsrf_calls = [c for c in self.calls if "xsrf-token" in c[1]]
        self.assertEqual(len(xsrf_calls), 1)

    def test_favorites_403_retries_with_fresh_xsrf(self):
        self._mock_raw({
            ("GET", f"{A.OAUTH_API}/xsrf-token"): [
                FakeResponse(200, {"xsrfToken": "fake-xsrf-1"}),
                FakeResponse(200, {"xsrfToken": "fake-xsrf-2"}),
            ],
            ("DELETE", f"{A.FAVORITES_API}/favorites/{FAKE_SKU}"): [
                FakeResponse(403, {}),
                FakeResponse(200, {}),
            ],
        })
        out = A.remove_favorite(FAKE_SKU)
        self.assertTrue(out["removed"])
        delete_calls = [c for c in self.calls if c[0] == "DELETE"]
        self.assertEqual(len(delete_calls), 2)
        self.assertEqual(delete_calls[0][2]["X-XSRF-TOKEN"], "fake-xsrf-1")
        self.assertEqual(delete_calls[1][2]["X-XSRF-TOKEN"], "fake-xsrf-2")


class TestRefreshFlow(AccountTestCase):
    def test_401_refresh_then_retry(self):
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): [
                FakeResponse(401, _read_json("account-401.json")),
                FakeResponse(200, {"items": []}),
            ],
            ("GET", f"{A.OAUTH_API}/xsrf-token"): FakeResponse(
                200, {"xsrfToken": "fake-xsrf-token"}
            ),
            ("POST", f"{A.OAUTH_API}/refresh-token"): FakeResponse(
                200, {},
                headers={"set-cookie": [
                    "jwt=new-fake-jwt; Path=/; HttpOnly",
                    "hpJwtToken=new-fake-hp-jwt; Path=/; HttpOnly",
                ]},
            ),
        })
        out = A.view_cart()
        self.assertEqual(out["items"], [])
        basket_calls = [c for c in self.calls if "basket/all" in c[1]]
        self.assertEqual(len(basket_calls), 2)
        # The retry used the refreshed cookies, not the originals.
        self.assertEqual(basket_calls[1][2]["HPBearer"], "new-fake-hp-jwt")
        self.assertIn("hpJwtToken=new-fake-hp-jwt", basket_calls[1][2]["Cookie"])
        # Refresh itself sent the XSRF header.
        refresh_calls = [c for c in self.calls if "refresh-token" in c[1]]
        self.assertEqual(refresh_calls[0][2]["X-XSRF-TOKEN"], "fake-xsrf-token")

    def test_401_refresh_without_cookies_is_expired(self):
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): FakeResponse(
                401, _read_json("account-401.json")
            ),
            ("GET", f"{A.OAUTH_API}/xsrf-token"): FakeResponse(
                200, {"xsrfToken": "fake-xsrf-token"}
            ),
            ("POST", f"{A.OAUTH_API}/refresh-token"): FakeResponse(200, {}),
        })
        with self.assertRaises(A.SessionExpired) as ctx:
            A.view_cart()
        self.assertIn("session expired", str(ctx.exception))

    def test_401_refresh_fails_is_expired(self):
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): FakeResponse(
                401, _read_json("account-401.json")
            ),
            ("GET", f"{A.OAUTH_API}/xsrf-token"): FakeResponse(
                200, {"xsrfToken": "fake-xsrf-token"}
            ),
            ("POST", f"{A.OAUTH_API}/refresh-token"): FakeResponse(401, {}),
        })
        with self.assertRaises(A.SessionExpired):
            A.view_cart()

    def test_401_after_refresh_is_expired(self):
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): [
                FakeResponse(401, _read_json("account-401.json")),
                FakeResponse(401, _read_json("account-401.json")),
            ],
            ("GET", f"{A.OAUTH_API}/xsrf-token"): FakeResponse(
                200, {"xsrfToken": "fake-xsrf-token"}
            ),
            ("POST", f"{A.OAUTH_API}/refresh-token"): FakeResponse(
                200, {},
                headers={"set-cookie": ["jwt=new-fake-jwt; Path=/"]},
            ),
        })
        with self.assertRaises(A.SessionExpired):
            A.view_cart()
        # Exactly one refresh attempt, one retry — no infinite loop.
        self.assertEqual(
            len([c for c in self.calls if "refresh-token" in c[1]]), 1
        )
        self.assertEqual(
            len([c for c in self.calls if "basket/all" in c[1]]), 2
        )


class TestErrorHandling(AccountTestCase):
    def test_429_and_500_messages(self):
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): FakeResponse(429, {}),
        })
        with self.assertRaises(A.AccountError) as ctx:
            A.view_cart()
        self.assertIn("429", str(ctx.exception))

        self.calls.clear()
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): FakeResponse(
                500, {"Message": "Internal Server Error"}
            ),
        })
        with self.assertRaises(A.AccountError) as ctx:
            A.view_cart()
        self.assertIn("500", str(ctx.exception))
        self.assertIn("Internal Server Error", str(ctx.exception))

    def test_errors_never_contain_session_material(self):
        self._mock_raw({
            ("GET", f"{A.BASKET_WEB_API}/basket/all"): FakeResponse(500, {}),
        })
        try:
            A.view_cart()
        except A.AccountError as e:
            self.assertNotIn("fake-jwt-token", str(e))
            self.assertNotIn("fake-hp-jwt-token", str(e))
        else:
            self.fail("expected AccountError")


class TestListingInfo(unittest.TestCase):
    def test_parse_listing_info(self):
        html = _read("product-listing-ids.html")
        info = P.parse_listing_info(html, sku=FAKE_SKU)
        self.assertEqual(info["listing_id"], FAKE_LISTING)
        self.assertEqual(info["product_id"], FAKE_PRODUCT)
        self.assertEqual(
            info["merchant_id"], "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        )

    def test_parse_listing_info_wrong_sku_ignored(self):
        html = _read("product-listing-ids.html")
        info = P.parse_listing_info(html, sku="HBCV99999XXXXX")
        # reduxStore product is for another SKU; only the listing_ids
        # array fallback (first element) may still apply.
        self.assertEqual(info.get("listing_id"), FAKE_LISTING)
        self.assertNotIn("product_id", info)
        self.assertNotIn("merchant_id", info)

    def test_parse_listing_info_array_fallback(self):
        html = '<html><body>{"listing_ids":["%s"]}</body></html>' % FAKE_LISTING
        info = P.parse_listing_info(html)
        self.assertEqual(info, {"listing_id": FAKE_LISTING})

    def test_parse_listing_info_absent(self):
        self.assertEqual(P.parse_listing_info("<html></html>"), {})

    def test_product_detail_includes_listing_fields(self):
        html = _read("product-listing-ids.html")
        detail = P.parse_product_detail(html)
        self.assertEqual(detail["sku"], FAKE_SKU)
        self.assertEqual(detail["listing_id"], FAKE_LISTING)
        self.assertEqual(detail["product_id"], FAKE_PRODUCT)
        self.assertEqual(
            detail["merchant_id"], "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        )

    def test_product_detail_omits_listing_fields_when_absent(self):
        # The trimmed 2026-11-06 fixture has no reduxStore / listing_ids.
        detail = P.parse_product_detail(_read("product-iphone15.html"))
        self.assertNotIn("listing_id", detail)
        self.assertNotIn("product_id", detail)
        self.assertNotIn("merchant_id", detail)


if __name__ == "__main__":
    unittest.main()
