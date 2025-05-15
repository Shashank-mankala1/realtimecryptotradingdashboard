import duckdb
import pandas as pd

# Path to your DuckDB file
duckdb_file = "/data/crypto.duckdb"  # Change this to your actual file path

# Number of predictions to show
N = 20

# Connect and fetch the last N predictions
with duckdb.connect(duckdb_file) as conn:
    query = f"""
        SELECT *
        FROM predictions
        ORDER BY interval_start DESC
        LIMIT {N}
    """
    df = conn.execute(query).fetchdf()

# Display the results
print(df)
