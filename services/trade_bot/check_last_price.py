import duckdb
import pandas as pd

# Path to your DuckDB file
DUCKDB_FILE = "/data/crypto.duckdb"


def run_query(sql):
    with duckdb.connect(DUCKDB_FILE) as conn:
        df = conn.execute(sql).fetchdf()
    return df


if __name__ == "__main__":
    # Example: Show latest 5 candles
    sql1 = "SELECT interval_end, close FROM candles ORDER BY interval_end DESC LIMIT 6;"
    print("Latest 5 candles:")
    print(run_query(sql1))
    print("\n")

    # Example: Show latest 5 tradebot_state rows
    sql2 = "SELECT * FROM tradebot_state ORDER BY last_update DESC LIMIT 15;"
    print("Latest 15 tradebot_state rows:")
    print(run_query(sql2))
    print("\n")
