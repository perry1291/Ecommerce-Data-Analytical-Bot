# SalesIQ — E-commerce Analytics Bot

Ask analytical questions about e-commerce sales data in plain English and
get real, computed answers — no dashboard, no pre-built charts, no SQL
knowledge required. Built as a text-to-SQL system: a natural-language
question is translated into SQL by an LLM, executed against a real
database, and the result is translated back into a plain-English answer.

## How it works

```
User question  →  Gemini writes SQL  →  DuckDB runs it  →  Gemini writes the answer  →  Chat
```

1. The user asks a question in the Streamlit chat.
2. Gemini receives the question plus a description of the database schema
   (table/column names only — never the actual data) and returns a SQL
   query.
3. The query is checked against a strict allow-list (SELECT only, no
   DDL/DML) before it's allowed to run.
4. DuckDB executes the query against the local database and returns the
   result.
5. Gemini turns that result into a short, plain-English answer.
6. The chat shows the answer, with an expandable panel showing the exact
   SQL and raw result underneath, for transparency.

If a question can't be answered from the available data (e.g. asking for
customer lifetime value in a dataset with no customer ID), the bot is
instructed to say so explicitly rather than guess.

## Dataset

Source: [Kaggle — e-comm-dataset](https://www.kaggle.com/datasets/mukundsavaliya/e-comm-dataset),
a real export from an Indian e-commerce clothing brand. The download
actually contains 7 CSVs; this project uses 2 of them:

- **Amazon Sale Report.csv** — 128,975 rows, one row per order line item,
  Amazon India domestic sales (Mar–Jun 2022). Loaded as the `orders` table.
- **Sale Report.csv** — 9,271 rows, one row per SKU, current inventory.
  Loaded as the `stock` table.

The remaining 5 files (international sales, cross-marketplace pricing
sheets, a warehouse rate card, and an expense ledger) were set aside — a
deliberate scoping decision to keep the bot's generated SQL reliable,
rather than adding join complexity across five differently-shaped tables
on day one.

## Data cleaning & feature engineering

Raw data had real quality issues, each addressed in `feature_engineering.py`:

| Issue found | Fix applied |
|---|---|
| `Status` had 13 messy, overlapping free-text values (e.g. "Shipped - Lost in Transit") | Collapsed into 6 clean categories: `status_group` (Delivered / Cancelled / Returned / In Transit / Pending / Lost-Damaged), plus boolean flags like `is_cancelled` |
| `amount` was null for ~7.8k rows, almost all cancelled orders with `qty = 0` | Filled with 0 rather than dropped — keeps cancellations in order counts without inflating revenue |
| `promotion-ids` was a 500+ character concatenated string when present | Replaced with a boolean `promo_applied` |
| `currency` was always the constant "INR" (no signal); `fulfilled-by` was only ever null or "Easy Ship" | Dropped `currency`; converted `fulfilled-by` to boolean `is_easy_ship` |
| Dates were stored as plain text | Parsed into real datetime values; derived `order_month`, `order_weekday`, `is_weekend` |
| City/state names had inconsistent casing (fragmenting `GROUP BY` results) | Standardized with `.str.title().str.strip()` |
| No price-per-unit column | Computed `unit_price = amount / qty` |
| **`stock.stock_category` uses a different taxonomy than `orders.category`** (e.g. "AN : LEGGINGS" vs "kurta") | The two tables are only ever joined on `sku`, never on category |

## Tech stack

| Tool | Role |
|---|---|
| Python | Glue language |
| pandas | Data cleaning and feature engineering |
| pyarrow | Parquet read/write support |
| DuckDB | Embedded analytical database — stores and queries the data |
| Gemini API (`google-genai`) | Question → SQL, and result → plain English |
| Streamlit | Chat UI |
| python-dotenv | Loads the API key from `.env` |

## Project structure

```
feature_engineering.py   # raw CSV -> cleaned/engineered parquet
build_db.py               # parquet + stock CSV -> ecomm.duckdb
bot.py                     # question -> SQL -> answer (core logic, no UI)
app.py                     # Streamlit chat UI
view_data.py               # utility: preview the cleaned data / export samples
ecomm.duckdb               # prebuilt database - ready to query, no setup needed
requirements.txt
.env.example
```

## Setup

```bash
git clone <your-repo-url>
cd salesiq
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then paste in your real Gemini API key
streamlit run app.py
```

Get a free Gemini API key at
[aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
(no credit card required).

`ecomm.duckdb` is already built and committed to this repo, so the app
runs immediately after cloning — no need to re-download the dataset or
re-run the feature engineering scripts unless you want to modify them.

## Example questions

- "What's our total revenue?"
- "Which category sells the most?"
- "What's the cancellation rate by state?"
- "Compare average order value: Amazon-fulfilled vs merchant-fulfilled"
- "Which top-selling SKUs are almost out of stock?"

## Extending it

- Add `International sale Report.csv` as a second table for domestic vs
  international comparisons. Its raw columns are `DATE`, `Months`,
  `CUSTOMER`, `Style`, `SKU`, `Size`, `PCS`, `RATE`, `GROSS AMT` — map
  these to a schema compatible with `orders` (e.g. `PCS` → `qty`,
  `GROSS AMT` → `amount`) before loading it as a third DuckDB table.
- If the free tier's rate limit gets in your way, or the bot's SQL is
  wrong on tricky questions, `bot.py` isolates the model name in one
  constant (`MODEL = "gemini-3.5-flash-lite"`) — swapping models or
  providers only touches that one file.
- Add a second self-correction retry loop in `ask_bot()` if one retry
  isn't enough for harder questions.

## Known limitations

- No customer identifier in the source data — the bot correctly declines
  customer-level questions (lifetime value, repeat purchase rate) instead
  of guessing.
- Single-join scope — only `orders` and `stock` are connected; the other
  5 raw files aren't wired in (see Dataset section).
- Gemini's free tier has rate limits (a handful of requests per minute) —
  fine for demo use, not for production traffic.
- The LLM's SQL can occasionally be *valid but not quite what was meant*
  (e.g. ambiguous phrasing like "top-selling" or "almost out of stock").
  The SQL-reveal panel exists specifically so this is always checkable.

## License / data attribution

Dataset used under Kaggle's terms via the source link above. This project
(code) is provided as-is for portfolio/demo purposes.
