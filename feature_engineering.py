"""
Feature engineering for the Amazon Sale Report table.

Input:  data/Amazon Sale Report.csv   (raw, as downloaded from Kaggle)
Output: data/amazon_sales_features.parquet

Run:  python feature_engineering.py
"""

import numpy as np 
import pandas as pd

RAW_PATH = "data/Amazon Sale Report.csv"
OUT_PATH = "data/amazon_sales_features.parquet"


def status_group(status: str) -> str:
    """Collapse the ~13 messy 'Status' strings (e.g. 'Shipped - Delivered to
    Buyer', 'Shipped - Lost in Transit') into a handful of clean categories
    that are actually useful to group/filter by."""
    s = status.lower()
    if "cancel" in s:
        return "Cancelled"
    if "return" in s or "rejected" in s:
        return "Returned"
    if "lost" in s or "damaged" in s:
        return "Lost/Damaged"
    if "delivered" in s:
        return "Delivered"
    if "pending" in s:
        return "Pending"
    if "shipped" in s or "shipping" in s:
        return "In Transit"
    return "Other"


def main():
    df = pd.read_csv(RAW_PATH, low_memory=False)

    # --- Drop junk columns ---
    # 'Unnamed: 22' is 99% empty (a stray trailing column in the export).
    # 'currency' is always "INR" - a constant column carries no signal.
    # 'index' just duplicates the row number.
    df = df.drop(columns=["Unnamed: 22", "currency", "index"], errors="ignore")
    df = df.rename(columns={"Sales Channel ": "Sales Channel"})  # trailing space typo

    # --- Types ---
    df["Date"] = pd.to_datetime(df["Date"], format="%m-%d-%y")

    # --- Clean status into an analyzable category ---
    df["status_group"] = df["Status"].apply(status_group)
    df["is_cancelled"] = df["status_group"] == "Cancelled"
    df["is_returned"] = df["status_group"] == "Returned"
    df["is_delivered"] = df["status_group"] == "Delivered"

    # --- Revenue features ---
    # Amount is null for ~7.8k rows, almost all of which are Qty=0 cancellations.
    df["Amount"] = df["Amount"].fillna(0)
    df["unit_price"] = np.where(df["Qty"] > 0, df["Amount"] / df["Qty"], 0)

    # --- Time features ---
    df["order_month"] = df["Date"].dt.to_period("M").astype(str)
    df["order_weekday"] = df["Date"].dt.day_name()
    df["is_weekend"] = df["Date"].dt.weekday >= 5

    # --- Fulfilment / promo features ---
    # 'Fulfilment' = Amazon (FBA) vs Merchant (FBM, seller ships it themself).
    df["is_fba"] = df["Fulfilment"] == "Amazon"
    # 'fulfilled-by' is only ever null or "Easy Ship" -> turn into a flag.
    df["is_easy_ship"] = df["fulfilled-by"].notna()
    # 'promotion-ids' is a huge concatenated string (500+ chars) when present -
    # not useful as raw text for a query bot, but "was a promo applied" is.
    df["promo_applied"] = df["promotion-ids"].notna()
    df = df.drop(columns=["fulfilled-by", "promotion-ids"])

    # --- Geography cleanup ---
    df["ship-state"] = df["ship-state"].str.title().str.strip()
    df["ship-city"] = df["ship-city"].str.title().str.strip()

    # --- Rename the remaining ship-* columns to be SQL/Streamlit friendly ---
    df = df.rename(columns={
        "Order ID": "order_id",
        "Date": "order_date",
        "Status": "status_raw",
        "Fulfilment": "fulfilment",
        "Sales Channel": "sales_channel",
        "ship-service-level": "ship_service_level",
        "Style": "style",
        "SKU": "sku",
        "Category": "category",
        "Size": "size",
        "ASIN": "asin",
        "Courier Status": "courier_status",
        "Qty": "qty",
        "Amount": "amount",
        "ship-city": "ship_city",
        "ship-state": "ship_state",
        "ship-postal-code": "ship_postal_code",
        "ship-country": "ship_country",
        "B2B": "is_b2b",
    })

    df.to_parquet(OUT_PATH, index=False)
    print(f"Wrote {len(df):,} rows x {len(df.columns)} columns -> {OUT_PATH}")
    print(df.dtypes)


if __name__ == "__main__":
    main()
