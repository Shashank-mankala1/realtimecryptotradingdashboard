import duckdb
import pandas as pd

# Parameters
CSV_FILES = [
    "/data/historical/kraken_trades_since_1743811200.csv",
    "/data/historical/kraken_trades_since_1746111528.csv",
    # Add more CSV file paths here
]
DUCKDB_FILE = "/data/crypto.duckdb"  # Output DuckDB file
TABLE_NAME = "candles"
CANDLE_INTERVAL = "1min"  # Candle interval (e.g., '1min', '5min')
SYMBOL = "BTC_USD"  # Symbol name

# Load and concatenate data from all CSV files
trades_list = [pd.read_csv(csv_file, parse_dates=["time"]) for csv_file in CSV_FILES]
trades = pd.concat(trades_list, ignore_index=True)

# Deduplicate on trade_id
trades = trades.drop_duplicates(subset="trade_id")

# Round time to candle interval (this is the interval start)
trades["interval_start"] = trades["time"].dt.floor(CANDLE_INTERVAL)

# Determine the last full candle time (exclude the last potentially unfinished one)
candle_cutoff = trades["interval_start"].unique()
if len(candle_cutoff) > 1:
    last_full_candle_time = sorted(candle_cutoff)[-2]
else:
    last_full_candle_time = None

# Filter out the last potentially unfinished candle
if last_full_candle_time is not None:
    trades = trades[trades["interval_start"] <= last_full_candle_time]

# Compute interval_end
trades["interval_end"] = trades["interval_start"] + pd.to_timedelta(CANDLE_INTERVAL)

# Aggregate into candles
candles = (
    trades.groupby("interval_start")
    .agg(
        interval_end=("interval_end", "first"),
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("volume", "sum"),
        trade_count=("price", "count"),
    )
    .reset_index()
)

# Add symbol field
candles["symbol"] = SYMBOL

# Reorder columns to match the required output
candles = candles[
    [
        "symbol",
        "interval_start",
        "interval_end",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trade_count",
    ]
]

# Ensure timezone-aware strings (UTC)
candles["interval_start"] = candles["interval_start"].dt.tz_localize("UTC").astype(str)
candles["interval_end"] = candles["interval_end"].dt.tz_localize("UTC").astype(str)
candles = candles.sort_values("interval_start").reset_index(drop=True)

# Write to DuckDB
duckdb_conn = duckdb.connect(DUCKDB_FILE)
duckdb_conn.execute(
    f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} AS SELECT * FROM candles LIMIT 0"
)
duckdb_conn.register("candles_df", candles)
duckdb_conn.execute(f"INSERT INTO {TABLE_NAME} SELECT * FROM candles_df")
duckdb_conn.close()

print(f"Wrote {len(candles)} candles to {DUCKDB_FILE} in table '{TABLE_NAME}'")
if last_full_candle_time is not None:
    print(f"Last full candle timestamp: {last_full_candle_time}")
