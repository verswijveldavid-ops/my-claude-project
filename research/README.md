# Product Research Automation

Runs Meta Ads Library → Google Trends → Shopify competitor scraper in one command.

## Setup (one time)

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

```powershell
# Full research on a keyword + competitor store
python run_research.py "ribbed lounge set" --shopify https://somestore.com

# Different country (NL or BE)
python run_research.py "fleece set" --shopify https://somestore.com --country NL

# Skip a step
python run_research.py "velvet lounge set" --skip-meta --shopify https://somestore.com
```

## What it does

| Step | Tool | Output |
|------|------|--------|
| 1/3 | Meta Ads Library | Active ad count, advertisers running 10-50+ ads (scaling signal) |
| 2/3 | Google Trends | 5-year trend, growing/flat/declining label, rising related searches |
| 3/3 | Shopify scraper | Full product list, hero product, price range, keyword matches |

Results are saved to `output/` as JSON, CSV, and XLSX files.

## Country codes
- UK → `GB`
- Netherlands → `NL`
- Belgium → `BE`
