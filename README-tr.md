# hepsiburada-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/hepsiburada-mcp

Türkiye'nin önde gelen e-ticaret pazaryeri **hepsiburada.com** için resmi
olmayan MCP sunucusu — milyonlarca üründe arama yapın, ürün detaylarını
okuyun (fiyat, stok, satıcı, GTIN, öne çıkan özellikler), müşteri
yorumlarını okuyun, 9 ana kategoriye göz atın ve herhangi bir sorgu için
fiyat istatistikleri (min / medyan / ortalama / maks) alın. Salt okunur
araçlar giriş gerektirmez. İsteğe bağlı **hesap işlemleri** (sepet +
favoriler) kendi tarayıcı oturumunuzu kullanır; oturum yalnızca MCP
yapılandırmanızda saklanır — bkz. [Hesap işlemleri](#hesap-i̇şlemleri).

> Mohammad Abbasi tarafından "Turkey MCP factory" (Sepehr tarzı süreç)
> kapsamında geliştirildi. hepsiburada.com ile bağlantısı yoktur.

## Yapay zekâ ajanları için

MCP istemci yapılandırmanıza ekleyin (stdio):

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

veya yerel çalıştırın: `python -m hepsiburada_mcp.server`
(`mcp<2`, `curl-cffi` gerekir).

Hesap işlemleri (sepet + favoriler) için tarayıcı oturum çerezinizi
yapılandırmaya ekleyin — bkz. [Hesap işlemleri](#hesap-i̇şlemleri):

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

## Araçlar

| Araç | Açıklama |
|------|----------|
| `hepsiburada_search` | Anahtar kelimeyle ürün arama — `query` ("iphone", "kablosuz kulaklık"), `sort` ("relevance" / "price_asc" / "price_desc"), `limit` 1..24, `page` 1'den başlar; başlık, TL fiyat, puan, yorum sayısı, URL, SKU, görsel, kampanya döndürür |
| `hepsiburada_product_detail` | Bir ürünün detayı (`product` = "-p-HBCV…" içeren URL veya yol): ad, marka, TL fiyat, stok durumu, puan, yorum sayısı, satıcı (+ resmi satıcı işareti), kategori yolu, renk, GTIN, görseller, öne çıkanlar, ayrıca `listing_id` / `product_id` / `merchant_id` (hesap işlemleri için) |
| `hepsiburada_list_categories` | 9 ana kategori: Türkçe ad, URL, kategori kimliği |
| `hepsiburada_price_stats` | Bir sorgunun fiyat istatistikleri: adet, min / medyan / ortalama / maks fiyat (TL) |
| `hepsiburada_product_reviews` | Bir ürünün son müşteri yorumları: yazar, yıldız puanı, yorum metni, tarih |
| `hepsiburada_view_cart` | Sepetiniz: ürünler (sepet öğesi kimliği, SKU, ad, adet, TL fiyat, seçili / sonra-al), toplam ürün sayısı ve toplam fiyat, ayrıca sepet URL'si — `HEPSIBURADA_SESSION` gerekir |
| `hepsiburada_add_to_cart` | Sepete ürün ekler (`sku`, `listing_id` veya `product_url`, `quantity` 1..99) — oturum + `confirm=true` gerekir |
| `hepsiburada_remove_from_cart` | Sepetten bir ürün çıkarır (`basket_item_id`, `hepsiburada_view_cart` çıktısındaki GUID; `basket_type` "Primary" / "Secondary") — oturum + `confirm=true` gerekir |
| `hepsiburada_update_cart_quantity` | Bir sepet ürününün adedini değiştirir (`basket_item_id`, `quantity` 1..99) — oturum + `confirm=true` gerekir |
| `hepsiburada_list_favorites` | Favori ürün SKU'larınız — `HEPSIBURADA_SESSION` gerekir |
| `hepsiburada_add_favorite` | Favorilere ürün ekler (`sku`, `listing_id` + `product_id` veya `product_url`) — oturum + `confirm=true` gerekir |
| `hepsiburada_remove_favorite` | Favorilerden ürün çıkarır (`sku`) — oturum + `confirm=true` gerekir |

Örnek çıktı (`hepsiburada_search` / "iphone"):

```json
{"query": "iphone", "count": 3, "products": [
  {"title": "Apple iPhone 15 128 GB Mavi",
   "url": "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK",
   "sku": "HBCV00004X9ZCK", "price_try": 56999.0, "rating": 4.8,
   "review_count": 13102}, …]}
```

## Hesap işlemleri

Sepet ve favori araçları **kendi tarayıcı oturumunuzla** çalışır — şifre
yok, API anahtarı yok, hiçbir yerde hesap oluşturulmaz. Oturum yalnızca
kendi makinenizdeki MCP istemci yapılandırmanızda bulunur ve yalnızca
hepsiburada.com'a gönderilir. Sunucu onu asla kaydetmez, yazdırmaz veya
saklamaz; hiçbir araç çıktısında görünmez. Her değişiklik (ekleme /
çıkarma / adet değiştirme) ayrıca `confirm=true` gerektirir; aksi
halde hiçbir işlem yapılmaz.

### Kurulum (bir kez)

1. Tarayıcınızda (Chrome / Edge / Firefox)
   [hepsiburada.com](https://www.hepsiburada.com)'a giriş yapın.
2. Geliştirici Araçları'nı açın (F12) → **Network** sekmesi → sayfayı
   yenileyin.
3. `hepsiburada.com` adresine yapılan herhangi bir isteğe tıklayın →
   **Headers** → **Cookie** istek başlığını bulun → değerinin tamamını
   kopyalayın.
   (Alternatif: Geliştirici Araçları → **Application** → **Cookies** →
   `https://www.hepsiburada.com` — ancak Network sekmesindeki Cookie
   başlığı tam değerdir; onu kopyalayın.)
4. Değeri MCP istemci yapılandırmanıza `HEPSIBURADA_SESSION` olarak
   yapıştırın (yukarıdaki örneğe bakın) ve MCP sunucusunu yeniden
   başlatın.
5. `hepsiburada_view_cart` aracını deneyin — gerçek sepetiniz
   görünmelidir.

### Notlar

- Oturumun süresi dolar: bir araç "session expired" derse, taze
  çerezler için 2–4. adımları tekrarlayın. hepsiburada.com'dan çıkış
  yapmak oturumu hemen geçersiz kılar.
- **Çerez değerini asla paylaşmayın** — elinde bulunduran herkes
  Hepsiburada hesabınıza tam erişim kazanır (sepet, favoriler,
  siparişler). Sohbetlere, issue'lara veya ekran görüntülerine
  yapıştırmayın.
- Hesap işlemleri bilinçli olarak dardır: sepet (görüntüleme / ekleme /
  çıkarma / adet değiştirme) ve favoriler (listeleme / ekleme /
  çıkarma). Ödeme, kupon veya toplu işlem yoktur.
- `listing_id` / `product_id`, `hepsiburada_product_detail`
  aracından alınır; veya ekleme araçlarına `product_url` verirseniz
  ürün sayfasından otomatik çözülür.

## Nasıl çalışır?

hepsiburada.com düz HTTP istemcilerine HTTP 403 döndürür; bu yüzden
aktarım Chrome TLS taklidi (`curl-cffi`, `chrome120`) kullanır. Herkese
açık bir JSON API yoktur — veriler sitenin sunucu taraflı işlenmiş
HTML sayfalarından gelir: arama sayfaları ürün kartları, ürün sayfaları
schema.org Product JSON-LD + satıcı bloğu + "Ürün Özellikleri" listesi,
ana sayfa ise ana kategorileri taşır. İstekler ~0.8 sn arayla yapılır;
salt okunur araçlar giriş gerektirmez, API anahtarı gerekmez. Hesap
araçları, tarayıcı oturumunuzla Hepsiburada'nın kendi ödeme / sepet /
favori API'lerini çağırır (bkz. [Hesap işlemleri](#hesap-i̇şlemleri));
uç noktalar canlı olarak doğrulandı (her biri oturumsuz HTTP 401
döndürür; bu da yolun + kimlik denetiminin doğru olduğunu kanıtlar).

## Kurulum

```bash
uvx hepsiburada-mcp==0.2.0        # doğrudan çalıştır (uv gerekir)
# veya
pip install hepsiburada-mcp==0.2.0
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
