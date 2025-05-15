import duckdb

# Connect to your DuckDB database or file
con = duckdb.connect("/data/crypto.duckdb")

# Delete the specific row using interval_start and trade_count
con.execute(
    """
    DELETE FROM candles
    WHERE interval_start = TIMESTAMP '2025-05-06 11:29:00+00:00'
      AND trade_count = 2
"""
)
