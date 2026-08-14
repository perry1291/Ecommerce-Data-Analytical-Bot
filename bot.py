"""
The bot's "brain": turns a plain-English question into SQL, runs it safely
against ecomm.duckdb, and turns the result back into a plain-English answer.

Uses Google's Gemini API (free tier).
"""
 
import os
import time
import duckdb
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash-lite"  # fast, free-tier friendly, good enough for SQL generation
DB_PATH = "ecomm.duckdb"

client = genai.Client()  # reads GEMINI_API_KEY from the environment
con = duckdb.connect(DB_PATH, read_only=True)

SCHEMA_DESCRIPTION = """
Table: orders  (one row per order line item, Amazon India domestic sales, Mar-Jun 2022)
  order_id, order_date, status_raw, status_group (Cancelled/Returned/Delivered/
  In Transit/Pending/Lost-Damaged/Other), fulfilment (Merchant/Amazon), sales_channel,
  ship_service_level, style, sku, category (Set/kurta/Western Dress/Top/Ethnic Dress/
  Bottom/Saree/Blouse/Dupatta), size, asin, courier_status, qty, amount (INR),
  unit_price, ship_city, ship_state, ship_postal_code, ship_country, is_b2b,
  is_cancelled, is_returned, is_delivered, order_month ('YYYY-MM'), order_weekday,
  is_weekend, is_fba (fulfilled by Amazon vs merchant self-ship), is_easy_ship,
  promo_applied

Table: stock  (one row per SKU, current inventory - NOT transactional, do not
  aggregate over time)
  sku, design_no, stock_qty, stock_category, size, color
  Note: stock_category uses a different taxonomy than orders.category - only
  join these two tables on sku, never on category.
"""

SYSTEM_PROMPT = f"""You write DuckDB SQL queries to answer analytical questions
about e-commerce data. Output ONLY the SQL query - no explanation, no markdown
code fences, no commentary.

Rules:
- Only SELECT statements. Never write INSERT/UPDATE/DELETE/DROP/ALTER/CREATE.
- Always add a LIMIT (e.g. LIMIT 50) unless the question calls for a single
  aggregate number.
- amount is in Indian Rupees (INR).
- Cancelled orders still appear in the table; filter status_group or
  is_cancelled if the question implies "actual"/"completed" sales.
- Default definition of "total revenue"/"total sales" (when not stated
  otherwise): SUM(amount) for all rows EXCEPT status_group = 'Cancelled'
  or 'Returned'. Only narrow further (e.g. to Delivered only) if the
  question explicitly asks for completed/delivered orders.
  - If a question needs something this schema cannot provide (e.g. a unique
  customer identifier - this dataset only has a ship-to postal code, which
  is a LOCATION, not a customer), do NOT substitute an unrelated column as
  a workaround. Output exactly: NO_ANSWER: <one short sentence explaining
  what's missing> and nothing else.

{SCHEMA_DESCRIPTION}"""


def _generate(prompt: str, system: str | None = None, max_retries: int = 3) -> str:
    """Call Gemini with a small retry loop - the free tier's rate limit is the
    most likely thing to fail during a live demo, so one retry is cheap insurance."""
    config = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=300,
    )
    wait = 2
    for attempt in range(max_retries):
        try:
            resp = client.models.generate_content(
                model=MODEL, contents=prompt, config=config
            )
            return resp.text.strip()
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(wait)
            wait *= 2
    raise RuntimeError("unreachable")


def question_to_sql(question: str) -> str:
    sql = _generate(question, system=SYSTEM_PROMPT)
    # strip stray markdown fences if the model adds them anyway
    return sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()


def is_safe(sql: str) -> bool:
    banned = ["insert", "update", "delete", "drop", "alter", "create",
              "attach", "copy", "pragma", "install"]
    lowered = sql.lower()
    return lowered.startswith("select") and not any(b in lowered for b in banned)


def run_query(sql: str):
    if not is_safe(sql):
        raise ValueError("Blocked: query was not a plain SELECT statement.")
    return con.execute(sql).fetchdf()


def answer_in_words(question: str, result_df) -> str:
    prompt = (
        f"Question: {question}\n\n"
        f"Query result:\n{result_df.to_string(index=False)}\n\n"
        "Answer the question in 1-3 plain sentences using this data. "
        "Amounts are in Indian Rupees - format as e.g. Rs. 12,345, never $. "
        "Do not mention SQL or the table. If the result is empty, say so plainly."
    )
    return _generate(prompt)


def ask_bot(question: str):
    """Returns (answer_text, sql_used, result_dataframe)."""
    sql = question_to_sql(question)
    if sql.startswith("NO_ANSWER"):
        reason = sql.split(":", 1)[1].strip() if ":" in sql else "the data doesn't support this."
        return f"I can't answer that from this data: {reason}", None, None
    try:
        result = run_query(sql)
    except Exception as e:
        # one self-correction attempt, feeding the actual error back
        fix_prompt = (
            f"This DuckDB SQL failed:\n{sql}\n\nError: {e}\n\n"
            "Output only the corrected SQL, nothing else."
        )
        sql = _generate(fix_prompt, system=SYSTEM_PROMPT)
        sql = sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
        result = run_query(sql)  # let it raise if it fails again

    answer = answer_in_words(question, result)
    return answer, sql, result


if __name__ == "__main__":
    # quick manual test from the command line
    if not os.environ.get("GEMINI_API_KEY"):
        print("Set GEMINI_API_KEY first (e.g. in a .env file).")
    else:
        q = "Which product category had the highest cancellation rate?"
        answer, sql, df = ask_bot(q)
        print("Q:", q)
        print("SQL:", sql)
        print("A:", answer)
