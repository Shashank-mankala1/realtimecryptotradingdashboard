import duckdb
import pandas as pd

# Parameters
CSV_FILE = "/data/historical/kraken_trades_since_1746569353.csv"
DUCKDB_FILE = "/data/crypto.duckdb"
TABLE_NAME = "candles"
CANDLE_INTERVAL = "1min"
SYMBOL = "BTC_USD"

# Load gap trades
trades = pd.read_csv(CSV_FILE, parse_dates=["time"])
trades["interval_start"] = trades["time"].dt.floor(CANDLE_INTERVAL)
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
candles["symbol"] = SYMBOL

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
candles["interval_start"] = candles["interval_start"].dt.tz_localize("UTC").astype(str)
candles["interval_end"] = candles["interval_end"].dt.tz_localize("UTC").astype(str)
candles = candles.sort_values("interval_start").reset_index(drop=True)

duckdb_conn = duckdb.connect(DUCKDB_FILE)

inserted = 0

for _, row in candles.iterrows():
    symbol = row["symbol"]
    interval_start = row["interval_start"]

    # Check if a candle with the same interval_start and symbol already exists
    result = duckdb_conn.execute(
        f"""
        SELECT trade_count
        FROM {TABLE_NAME}
        WHERE interval_start = ? AND symbol = ?
        """,
        [interval_start, symbol],
    ).fetchone()

    if result is None:
        # Insert if it does not exist
        duckdb_conn.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                symbol, interval_start, interval_end, open, high, low, close, volume, trade_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row["symbol"],
                row["interval_start"],
                row["interval_end"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                int(row["trade_count"]),
            ],
        )
        inserted += 1
        print(f"Inserted: {row.to_dict()}")
    else:
        existing_trade_count = result[0]
        if row["trade_count"] > existing_trade_count:
            # Replace with more complete candle
            duckdb_conn.execute(
                f"""
                UPDATE {TABLE_NAME}
                SET interval_end = ?, open = ?, high = ?, low = ?, close = ?, volume = ?, trade_count = ?
                WHERE symbol = ? AND interval_start = ?
                """,
                [
                    row["interval_end"],
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["volume"],
                    int(row["trade_count"]),
                    row["symbol"],
                    row["interval_start"],
                ],
            )
            inserted += 1
            print(f"Replaced due to higher trade_count: {row.to_dict()}")

duckdb_conn.close()
print(
    f"Inserted/Replaced {inserted} candles from gap file into {DUCKDB_FILE} in table '{TABLE_NAME}'"
)
