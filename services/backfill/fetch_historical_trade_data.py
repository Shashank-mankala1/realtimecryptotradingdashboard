## fetch_trade_data.py
import os
import random
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests


def fetch_trades(pair="XBTUSD", since=None, count=1000, retry_count=0):
    """Fetch trades from Kraken API with retry logic"""
    url = "https://api.kraken.com/0/public/Trades"
    params = {"pair": pair, "count": count}
    if since:
        params["since"] = since

    headers = {"Accept": "application/json"}

    if retry_count > 0:
        sleep_time = min(60, (2**retry_count) + random.uniform(0, 1))
        print(
            f"Rate limited. Backing off for {sleep_time:.2f} seconds (retry {retry_count})..."
        )
        time.sleep(sleep_time)
    else:
        time.sleep(0.8)

    try:
        response = requests.get(url, headers=headers, params=params)
        result = response.json()

        if (
            "error" in result
            and result["error"]
            and any("Too many requests" in err for err in result["error"])
        ):
            if retry_count < 5:
                return fetch_trades(pair, since, count, retry_count + 1)
            else:
                print("Maximum retries reached. Giving up on this request.")

        return result
    except Exception as e:
        print(f"Request error: {e}")
        if retry_count < 5:
            return fetch_trades(pair, since, count, retry_count + 1)
        return {"error": [str(e)]}


def main():
    pair = "XBTUSD"

    ## Two ways to do this: either use days ago or use timestamp.
    # To get the historical candles use days_ago.
    # To get the gap candles use start_timestamp with it being the last time from your historical candles

    # How many days ago
    days_ago = 30  # Change this value as needed

    # Calculate the date and time at midnight of 'days_ago'
    target_date = (datetime.now() - timedelta(days=days_ago)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # -------------------------------------------------------------------------------------------#
    # USE one or the other!!!
    # Convert to Unix timestamp (UTC-aware)
    start_timestamp = int(target_date.replace(tzinfo=timezone.utc).timestamp())

    start_timestamp = 1746569353

    # USE
    # -------------------------------------------------------------------------------------------#
    print("Start timestamp:", start_timestamp)
    print(
        f"Fetching trades for {pair} starting from: {datetime.fromtimestamp(start_timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    current_time = datetime.now(timezone.utc).timestamp()
    print(
        f"Current time: {datetime.fromtimestamp(current_time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    since = str(start_timestamp)
    all_trades = []
    batch_count = 0
    max_batches = 1000
    temp_files = []

    while batch_count < max_batches:
        batch_count += 1
        print(f"\nFetching batch {batch_count}...")

        response = fetch_trades(pair=pair, since=since, count=1000)

        if "error" in response and response["error"]:
            print(f"Error: {response['error']}")
            break

        if "result" not in response:
            print("Unexpected response format:", response)
            break

        result = response["result"]
        pair_key = next((k for k in result.keys() if k != "last"), None)

        if not pair_key:
            print("No trade data found in response")
            break

        trades = result[pair_key]
        if not trades:
            print("No trades in this batch")
            break

        batch_trades = []
        latest_trade_time = 0
        for trade in trades:
            trade_time = float(trade[2])
            latest_trade_time = max(latest_trade_time, trade_time)
            batch_trades.append(
                {
                    "price": float(trade[0]),
                    "volume": float(trade[1]),
                    "time": datetime.fromtimestamp(
                        trade_time, tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp": trade_time,
                    "type": "buy" if trade[3] == "b" else "sell",
                    "order_type": "market" if trade[4] == "m" else "limit",
                    "trade_id": trade[6] if len(trade) > 6 else None,
                }
            )

        all_trades.extend(batch_trades)
        print(f"Found {len(batch_trades)} trades in this batch")

        # NEW: Show progress in days fetched
        days_fetched = (latest_trade_time - start_timestamp) / (60 * 60 * 24)
        days_remaining = (current_time - latest_trade_time) / (60 * 60 * 24)
        latest_trade_date = datetime.fromtimestamp(
            latest_trade_time, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")
        print(f"Latest trade timestamp: {latest_trade_date} UTC")
        print(
            f"Progress: {days_fetched:.2f} days fetched | {days_remaining:.2f} days remaining"
        )

        if batch_count % 5 == 0:
            temp_df = pd.DataFrame(all_trades)
            temp_path = f"kraken_trades_progress_{batch_count}.csv"
            temp_df.to_csv(temp_path, index=False)
            temp_files.append(temp_path)
            print(f"Saved progress to {temp_path} ({len(temp_df)} trades)")

            if not temp_df.empty:
                min_date = datetime.fromtimestamp(
                    temp_df["timestamp"].min(), tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S")
                max_date = datetime.fromtimestamp(
                    temp_df["timestamp"].max(), tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S")
                days_covered = (
                    temp_df["timestamp"].max() - temp_df["timestamp"].min()
                ) / (60 * 60 * 24)
                print(
                    f"Current range: {min_date} to {max_date} UTC ({days_covered:.2f} days)"
                )

        if "last" in result:
            since = result["last"]
        else:
            print("No 'last' timestamp in response. Cannot continue.")
            break

        if latest_trade_time >= current_time:
            print("Reached current time. Stopping data collection.")
            break

    df = pd.DataFrame(all_trades)
    if df.empty:
        print("No trades were collected.")
        return pd.DataFrame()

    df = df.sort_values("timestamp", ascending=True)
    output_path = f"/data/historical/kraken_trades_since_{start_timestamp}.csv"
    df.to_csv(output_path, index=False)
    print(f"\nFinal data saved to: {output_path}")
    print(f"Total trades collected: {len(df)}")

    # Delete temp files
    for f in temp_files:
        try:
            os.remove(f)
            print(f"Deleted temp file: {f}")
        except Exception as e:
            print(f"Failed to delete temp file {f}: {e}")

    if not df.empty:
        min_date = datetime.fromtimestamp(
            df["timestamp"].min(), tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")
        max_date = datetime.fromtimestamp(
            df["timestamp"].max(), tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")
        days_covered = (df["timestamp"].max() - df["timestamp"].min()) / (60 * 60 * 24)
        print(f"Date range: {min_date} to {max_date} UTC")
        print(f"Total days covered: {days_covered:.2f}")

    print("\nSample of the data:")
    print(df.head())


if __name__ == "__main__":
    main()
