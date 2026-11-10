# hepsiburada-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/hepsiburada-mcp

سرور MCP غیررسمی و **فقط‌خواندنی** برای **hepsiburada.com**، بزرگ‌ترین
فروشگاه اینترنتی ترکیه — جست‌وجو در میلیون‌ها کالا، خواندن جزئیات کالا
(قیمت، موجودی، فروشنده، GTIN، ویژگی‌های برجسته)، خواندن نظرهای مشتریان،
مرور ۹ دسته‌ی اصلی، و گرفتن آمار قیمت (کمترین / میانه / میانگین /
بیشترین) برای هر جست‌وجو.

> ساخته‌ی محمد عباسی در چارچوب «کارخانه‌ی MCP ترکیه» (به سبک سپهر). هیچ
> وابستگی‌ای به hepsiburada.com ندارد.

## برای ایجنت‌های هوش مصنوعی

به پیکربندی MCP client خود اضافه کنید (stdio):

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

یا به‌صورت محلی اجرا کنید: `python -m hepsiburada_mcp.server`
(نیازمند `mcp<2` و `curl-cffi`).

## ابزارها

| ابزار | توضیح |
|------|-------|
| `hepsiburada_search` | جست‌وجوی کالا با کلیدواژه — `query` (مثل «iphone» یا «kablosuz kulaklık»)، `sort` (‏«relevance» / ‏«price_asc» / ‏«price_desc»)، `limit` از ۱ تا ۲۴، `page` از ۱؛ برمی‌گرداند: عنوان، قیمت به لیر، امتیاز، تعداد نظر، آدرس، SKU، عکس، کمپین |
| `hepsiburada_product_detail` | جزئیات یک کالا (`product` = آدرس کامل یا مسیر حاوی «-p-HBCV…»): نام، برند، قیمت به لیر، وضعیت موجودی، امتیاز، تعداد نظر، فروشنده (+ فروشنده‌ی رسمی)، مسیر دسته، رنگ، GTIN، عکس‌ها، ویژگی‌های برجسته |
| `hepsiburada_list_categories` | ۹ دسته‌ی اصلی: نام ترکی، آدرس، شناسه‌ی دسته |
| `hepsiburada_price_stats` | آمار قیمت برای یک جست‌وجو: تعداد، کمترین / میانه / میانگین / بیشترین قیمت (لیر) |
| `hepsiburada_product_reviews` | نظرهای اخیر مشتریان برای یک کالا: نویسنده، امتیاز ستاره‌ای، متن نظر، تاریخ |

نمونه‌ی خروجی (`hepsiburada_search` / ‏«iphone»):

```json
{"query": "iphone", "count": 3, "products": [
  {"title": "Apple iPhone 15 128 GB Mavi",
   "url": "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK",
   "sku": "HBCV00004X9ZCK", "price_try": 56999.0, "rating": 4.8,
   "review_count": 13102}, …]}
```

## چطور کار می‌کند؟

سایت hepsiburada.com به کلاینت‌های HTTP ساده خطای 403 می‌دهد؛ به همین
دلیل لایه‌ی انتقال از جعل TLS کروم (`curl-cffi`، ‏`chrome120`) استفاده
می‌کند. API عمومی JSON ندارد — داده‌ها از HTML رندرشده‌ی سمت سرور
می‌آیند: صفحه‌های جست‌وجو کارت‌های کالا دارند، صفحه‌های کالا JSON-LD از
نوع Product به‌همراه بلوک فروشنده و فهرست «Ürün Özellikleri»، و صفحه‌ی
اصلی دسته‌های اصلی را دارد. درخواست‌ها با فاصله‌ی حدود ۰٫۸ ثانیه
فرستاده می‌شوند؛ همه‌چیز فقط‌خواندنی است، بدون لاگین و بدون کلید API.

## نصب

```bash
uvx hepsiburada-mcp==0.1.1        # اجرای مستقیم (نیازمند uv)
# یا
pip install hepsiburada-mcp==0.1.1
hepsiburada-mcp            # اجرای سرور MCP روی stdio
```

## تست‌ها

```bash
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

تست‌های آفلاین روی نمونه‌های ضبط‌شده از صفحه‌های واقعی اجرا می‌شوند
(دریافت‌شده در ۲۰۲۶-۱۱-۰۶)؛ تست‌های زنده به hepsiburada.com وصل می‌شوند.

## لایسنس

MIT — ببینید [LICENSE](LICENSE).

---

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
