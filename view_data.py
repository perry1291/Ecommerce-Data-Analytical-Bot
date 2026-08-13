"""
Lets you actually SEE the cleaned data inside ecomm.duckdb - since the .duckdb
file itself can't be opened as text in VS Code.

Run:  python view_data.py
"""

import duckdb

con = duckdb.connect("ecomm.duckdb", read_only=True)

print("=" * 60)
print("ORDERS table - first 10 rows")
print("=" * 60)
print(con.execute("SELECT * FROM orders LIMIT 10").fetchdf().to_string())

print("\n" + "=" * 60)
print("STOCK table - first 10 rows")
print("=" * 60)
print(con.execute("SELECT * FROM stock LIMIT 10").fetchdf().to_string())

print("\n" + "=" * 60)
print("Column names and types - orders")
print("=" * 60)
print(con.execute("DESCRIBE orders").fetchdf().to_string())

# Export a readable sample you can open in Excel/Google Sheets
con.execute("""
    COPY (SELECT * FROM orders LIMIT 200)
    TO 'orders_sample.csv' (HEADER, DELIMITER ',')
""")
print("\nSaved orders_sample.csv (200 rows) - open it in Excel to browse visually.")

# Export the full stock table too (it's small - only ~9,000 rows)
con.execute("""
    COPY (SELECT * FROM stock)
    TO 'stock_sample.csv' (HEADER, DELIMITER ',')
""")
print("Saved stock_sample.csv (all rows) - open it in Excel to browse.")

con.close()