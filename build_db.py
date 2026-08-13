"""
Loads the engineered sales table (+ the stock master, for optional joins)
into a single DuckDB file that the bot queries.

Run:  python build_db.py
"""

import duckdb
 
con = duckdb.connect("ecomm.duckdb")

con.execute("""
    CREATE OR REPLACE TABLE orders AS
    SELECT * FROM 'data/amazon_sales_features.parquet'
""")

# Stock master - joinable to orders on sku. Kept as a separate table on
# purpose: it's a different grain (one row per SKU, not one row per order),
# and its 'Category' values use a different taxonomy than orders.category
# (e.g. "AN : LEGGINGS" vs "kurta") - so don't UNION them, only JOIN on sku.
con.execute("""
    CREATE OR REPLACE TABLE stock AS
    SELECT
        "SKU Code" AS sku,
        "Design No." AS design_no,
        "Stock" AS stock_qty,
        "Category" AS stock_category,
        "Size" AS size,
        "Color" AS color
    FROM read_csv_auto('data/Sale Report.csv')
""")

n_orders = con.execute("SELECT count(*) FROM orders").fetchone()[0]
n_stock = con.execute("SELECT count(*) FROM stock").fetchone()[0]
print(f"orders table: {n_orders:,} rows")
print(f"stock table:  {n_stock:,} rows")

con.close()
print("Wrote ecomm.duckdb")
