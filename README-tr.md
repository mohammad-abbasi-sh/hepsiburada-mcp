# hepsiburada-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/hepsiburada-mcp

Türkiye'nin önde gelen e-ticaret pazaryeri **hepsiburada.com** için resmi
olmayan, **salt okunur** MCP sunucusu — milyonlarca üründe arama yapın,
ürün detaylarını okuyun (fiyat, stok, satıcı, GTIN, öne çıkan özellikler),
müşteri yorumlarını okuyun, 9 ana kategoriye göz atın ve herhangi bir
sorgu için fiyat istatistikleri (min / medyan / ortalama / maks) alın.

> Mohammad Abbasi tarafından "Turkey MCP factory" (Sepehr tarzı süreç)
> kapsamında geliştirildi. hepsiburada.com ile bağlantısı yoktur.

## Yapay zekâ ajanları için

MCP istemci yapılandırmanıza ekleyin (stdio):

```json
{
  "mcpServers": {
    "hepsiburada": {
      "command": "uvx",
      "args": ["hepsiburada-mcp"]
    }
  }
}
```

veya yerel çalıştırın: `python -m hepsiburada_mcp.server`
(`mcp<2`, `curl-cffi` gerekir).

## Araçlar

| Araç | Açıklama |
|------|----------|
| `hepsiburada_search` | Anahtar kelimeyle ürün arama — `query` ("iphone", "kablosuz kulaklık"), `sort` ("relevance" / "price_asc" / "price_desc"), `limit` 1..24, `page` 1'den başlar; başlık, TL fiyat, puan, yorum sayısı, URL, SKU, görsel, kampanya döndürür |
| `hepsiburada_product_detail` | Bir ürünün detayı (`product` = "-p-HBCV…" içeren URL veya yol): ad, marka, TL fiyat, stok durumu, puan, yorum sayısı, satıcı (+ resmi satıcı işareti), kategori yolu, renk, GTIN, görseller, öne çıkanlar |
| `hepsiburada_list_categories` | 9 ana kategori: Türkçe ad, URL, kategori kimliği |
| `hepsiburada_price_stats` | Bir sorgunun fiyat istatistikleri: adet, min / medyan / ortalama / maks fiyat (TL) |
| `hepsiburada_product_reviews` | Bir ürünün son müşteri yorumları: yazar, yıldız puanı, yorum metni, tarih |

Örnek çıktı (`hepsiburada_search` / "iphone"):

```json
{"query": "iphone", "count": 3, "products": [
  {"title": "Apple iPhone 15 128 GB Mavi",
   "url": "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK",
   "sku": "HBCV00004X9ZCK", "price_try": 56999.0, "rating": 4.8,
   "review_count": 13102}, …]}
```

## Nasıl çalışır?

hepsiburada.com düz HTTP istemcilerine HTTP 403 döndürür; bu yüzden
aktarım Chrome TLS taklidi (`curl-cffi`, `chrome120`) kullanır. Herkese
açık bir JSON API yoktur — veriler sitenin sunucu taraflı işlenmiş
HTML sayfalarından gelir: arama sayfaları ürün kartları, ürün sayfaları
schema.org Product JSON-LD + satıcı bloğu + "Ürün Özellikleri" listesi,
ana sayfa ise ana kategorileri taşır. İstekler ~0.8 sn arayla yapılır;
her şey salt okunurdur, giriş gerekmez, API anahtarı gerekmez.

## Kurulum

```bash
uvx hepsiburada-mcp        # doğrudan çalıştır (uv gerekir)
# veya
pip install hepsiburada-mcp
hepsiburada-mcp            # MCP sunucusunu stdio üzerinde başlatır
```

## Testler

```bash
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

Çevrimdışı testler kayıtlı örnek sayfalarla çalışır (gerçek sayfalar,
2026-11-06); canlı testler hepsiburada.com'a bağlanır.

## Lisans

MIT — bkz. [LICENSE](LICENSE).
