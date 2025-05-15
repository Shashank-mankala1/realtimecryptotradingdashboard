import duckdb

DUCKDB_FILE = "/data/crypto.duckdb"
STATE_TABLE = "tradebot_state"

with duckdb.connect(DUCKDB_FILE) as conn:
    conn.execute(f"DROP TABLE IF EXISTS {STATE_TABLE}")
    print(f"Table '{STATE_TABLE}' has been dropped (reset).")
