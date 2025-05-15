import duckdb
import pandas as pd

# Connect to your DuckDB database
con = duckdb.connect("/data/crypto.duckdb")  # Replace with your database path

# Query to get the last 10 candles
query = """
SELECT *
FROM candles
ORDER BY interval_start DESC
LIMIT 1000
"""

# Execute and load into DataFrame
df = con.execute(query).fetchdf()

# Print the result
print(df)


# Convert columns to datetime
df["interval_start"] = pd.to_datetime(df["interval_start"])
df["interval_end"] = pd.to_datetime(df["interval_end"])

# Define target time and window
target_time = pd.Timestamp("2025-05-06 22:09:13", tz="UTC")
start_window = target_time - pd.Timedelta(minutes=3)
end_window = target_time + pd.Timedelta(minutes=3)

# Filter rows where interval overlaps with the window
filtered_df = df[
    (df["interval_end"] >= start_window) & (df["interval_start"] <= end_window)
]

print(filtered_df)
