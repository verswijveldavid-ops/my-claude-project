"""
Product Research Automation
Usage:
    python run_research.py "ribbed lounge set" --shopify https://somestore.myshopify.com
    python run_research.py "fleece set" --shopify https://somestore.com --country GB
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


# ─────────────────────────────────────────────
# 1. META ADS LIBRARY
# ─────────────────────────────────────────────
def run_meta_ads(keyword, country="GB"):
    separator("1/3 — META ADS LIBRARY")
    print(f"Searching for: '{keyword}'  |  Country: {country}")
    print("(This may take 30-60 seconds — Meta rate-limits requests)\n")

    try:
        from meta_ads_collector import MetaAdsCollector

        collector = MetaAdsCollector()
        ads = collector.collect(
            query=keyword,
            country=country,
            limit=100,
        )

        if not ads:
            print("No ads found — keyword may be too niche or Meta returned empty results.")
            return []

        # Summarise by advertiser
        by_advertiser = {}
        for ad in ads:
            name = ad.get("page_name") or ad.get("advertiser_name") or "Unknown"
            by_advertiser.setdefault(name, []).append(ad)

        print(f"Total active ads found : {len(ads)}")
        print(f"Unique advertisers     : {len(by_advertiser)}")
        print(f"Scaling signal (10-50+ ads from one store): ", end="")

        scaling = {k: len(v) for k, v in by_advertiser.items() if len(v) >= 10}
        if scaling:
            print(f"{len(scaling)} store(s)")
            for name, count in sorted(scaling.items(), key=lambda x: -x[1]):
                print(f"  • {name}: {count} ads")
        else:
            print("none detected")

        print("\nTop 10 advertisers by ad count:")
        for name, count in sorted(by_advertiser.items(), key=lambda x: -x[1])[:10]:
            print(f"  {count:>4}  {name}")

        # Save full data
        out_file = OUTPUT_DIR / f"meta_ads_{timestamp()}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(ads, f, indent=2, ensure_ascii=False)
        print(f"\nFull data saved → {out_file}")
        return ads

    except ImportError:
        print("ERROR: meta-ads-collector not installed. Run: pip install meta-ads-collector")
        return []
    except Exception as e:
        print(f"ERROR: {e}")
        print("Tip: Meta may be blocking requests. Try again in a few minutes or use a VPN/proxy.")
        return []


# ─────────────────────────────────────────────
# 2. GOOGLE TRENDS
# ─────────────────────────────────────────────
def run_google_trends(keyword, geo="GB"):
    separator("2/3 — GOOGLE TRENDS")
    print(f"Keyword: '{keyword}'  |  Region: {geo}")
    print("(Fetching 5-year trend — takes ~15 seconds due to rate limiting)\n")

    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-GB", tz=0, timeout=(10, 30), retries=3, backoff_factor=0.5)
        pytrends.build_payload([keyword], timeframe="today 5-y", geo=geo)

        df = pytrends.interest_over_time()

        if df.empty:
            print("No data returned — try a broader keyword.")
            return

        values = df[keyword].tolist()
        avg = sum(values) / len(values)
        recent_avg = sum(values[-12:]) / 12  # last ~3 months (weekly data)
        early_avg = sum(values[:12]) / 12

        print(f"Average interest (5yr) : {avg:.1f}/100")
        print(f"Recent 3-month avg     : {recent_avg:.1f}/100")
        print(f"Early period avg       : {early_avg:.1f}/100")

        if recent_avg > early_avg * 1.2:
            trend_label = "GROWING ↑"
        elif recent_avg < early_avg * 0.8:
            trend_label = "DECLINING ↓"
        else:
            trend_label = "FLAT →"

        print(f"Trend direction        : {trend_label}")
        print(f"Peak interest          : {max(values)}/100  (week of {df[keyword].idxmax().date()})")
        print(f"Current interest       : {values[-1]}/100")

        # Related queries
        try:
            related = pytrends.related_queries()
            rising = related.get(keyword, {}).get("rising")
            if rising is not None and not rising.empty:
                print("\nRising related searches:")
                for _, row in rising.head(5).iterrows():
                    print(f"  • {row['query']}  (+{row['value']}%)")
        except Exception:
            pass

        # Save CSV
        out_file = OUTPUT_DIR / f"google_trends_{timestamp()}.csv"
        df.to_csv(out_file)
        print(f"\nFull trend data saved → {out_file}")

    except ImportError:
        print("ERROR: pytrends not installed. Run: pip install pytrends")
    except Exception as e:
        print(f"ERROR: {e}")
        print("Tip: Google Trends rate-limits heavily. Wait 60 seconds and retry.")


# ─────────────────────────────────────────────
# 3. SHOPIFY STORE SCRAPER
# ─────────────────────────────────────────────
def run_shopify_scraper(store_url, keyword=None):
    separator("3/3 — SHOPIFY COMPETITOR STORE")

    import requests
    import pandas as pd

    # Normalise URL
    store_url = store_url.rstrip("/")
    if not store_url.startswith("http"):
        store_url = "https://" + store_url

    print(f"Store : {store_url}")
    if keyword:
        print(f"Filter: showing products matching '{keyword}' first\n")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    products = []
    page = 1

    print("Fetching products", end="", flush=True)
    while True:
        url = f"{store_url}/products.json?limit=250&page={page}"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                print(f"\nStore returned {r.status_code} — may not be a Shopify store or may block scrapers.")
                break
            data = r.json().get("products", [])
            if not data:
                break
            products.extend(data)
            print(".", end="", flush=True)
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"\nERROR fetching page {page}: {e}")
            break

    print(f" done\n")

    if not products:
        print("No products found.")
        return

    print(f"Total products in store : {len(products)}")

    # Build flat table
    rows = []
    for p in products:
        variants = p.get("variants", [{}])
        prices = [float(v.get("price", 0)) for v in variants if v.get("price")]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        price_str = f"£{min_price:.2f}" if min_price == max_price else f"£{min_price:.2f}–£{max_price:.2f}"

        rows.append({
            "title": p.get("title", ""),
            "product_type": p.get("product_type", ""),
            "price": price_str,
            "min_price_gbp": min_price,
            "variants": len(variants),
            "tags": ", ".join(p.get("tags", [])),
            "published_at": p.get("published_at", "")[:10],
            "handle": p.get("handle", ""),
            "url": f"{store_url}/products/{p.get('handle', '')}",
        })

    df = pd.DataFrame(rows)

    # Hero product = most expensive (common proxy for flagship item)
    hero = df.sort_values("min_price_gbp", ascending=False).iloc[0]
    print(f"Likely hero product     : {hero['title']} @ {hero['price']}")
    print(f"  URL: {hero['url']}")

    # Price distribution
    print(f"\nPrice range across store:")
    print(f"  Cheapest  : {df.sort_values('min_price_gbp').iloc[0]['price']}  ({df.sort_values('min_price_gbp').iloc[0]['title']})")
    print(f"  Most exp. : {df.sort_values('min_price_gbp', ascending=False).iloc[0]['price']}  ({df.sort_values('min_price_gbp', ascending=False).iloc[0]['title']})")

    # Keyword filter
    if keyword:
        kw = keyword.lower()
        matches = df[
            df["title"].str.lower().str.contains(kw) |
            df["tags"].str.lower().str.contains(kw) |
            df["product_type"].str.lower().str.contains(kw)
        ]
        print(f"\nProducts matching '{keyword}': {len(matches)}")
        for _, row in matches.head(10).iterrows():
            print(f"  • {row['title']}  {row['price']}  → {row['url']}")

    # Newest products (what they're actively adding)
    print(f"\n5 most recently added products:")
    for _, row in df.sort_values("published_at", ascending=False).head(5).iterrows():
        print(f"  {row['published_at']}  {row['title']}  {row['price']}")

    # Save
    out_file = OUTPUT_DIR / f"shopify_{timestamp()}.xlsx"
    df.to_excel(out_file, index=False)
    print(f"\nFull product list saved → {out_file}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Product research automation for Shopify dropshippers"
    )
    parser.add_argument("keyword", help='Product keyword, e.g. "ribbed lounge set"')
    parser.add_argument(
        "--shopify",
        metavar="URL",
        help="Competitor Shopify store URL, e.g. https://somestore.com",
    )
    parser.add_argument(
        "--country",
        default="GB",
        help="Country code for Meta Ads + Google Trends (default: GB). Use NL or BE for other markets.",
    )
    parser.add_argument(
        "--skip-meta",
        action="store_true",
        help="Skip Meta Ads step",
    )
    parser.add_argument(
        "--skip-trends",
        action="store_true",
        help="Skip Google Trends step",
    )

    args = parser.parse_args()

    print(f"\n{'#'*60}")
    print(f"  PRODUCT RESEARCH: {args.keyword.upper()}")
    print(f"  Country: {args.country}  |  {datetime.now().strftime('%d %b %Y %H:%M')}")
    print(f"{'#'*60}")

    if not args.skip_meta:
        run_meta_ads(args.keyword, country=args.country)
    else:
        print("\n[Skipped] Meta Ads")

    if not args.skip_trends:
        run_google_trends(args.keyword, geo=args.country)
    else:
        print("\n[Skipped] Google Trends")

    if args.shopify:
        run_shopify_scraper(args.shopify, keyword=args.keyword)
    else:
        print("\n[Skipped] Shopify scraper — no --shopify URL provided")
        print("  Add it like: --shopify https://somestore.com")

    print(f"\n{'='*60}")
    print(f"  Research complete. Results saved to: research/output/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
