import json

import duckdb
import pandas as pd
from confluent_kafka import Consumer, KafkaError, KafkaException
from predict import predict_and_save

TOPIC = "crypto-candles"
REDPANDA_BROKER = "redpanda-0:9092"
DUCKDB_FILE = "/data/crypto.duckdb"
TABLE_NAME = "candles"

DUCKDB_FIELDS = [
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


def parse_candle(candle):
    for key in ["interval_start", "interval_end"]:
        dt = pd.to_datetime(candle[key], utc=True)
        candle[key] = dt.strftime("%Y-%m-%d %H:%M:%S%z")
        # Insert colon into offset manually (e.g. from +0000 to +00:00)
        candle[key] = candle[key][:-2] + ":" + candle[key][-2:]
    return candle


def save_to_duckdb(candles):
    if not candles:
        return
    candles = [parse_candle(c) for c in candles]
    candles_df = pd.DataFrame(candles)
    try:
        candles_df = candles_df[DUCKDB_FIELDS]
    except KeyError as e:
        print("Missing field in candle:", e)
        return
    duckdb_conn = duckdb.connect(DUCKDB_FILE)
    duckdb_conn.register("candles_df", candles_df)
    duckdb_conn.execute(f"INSERT INTO {TABLE_NAME} SELECT * FROM candles_df")
    duckdb_conn.close()
    print(f"Wrote {len(candles)} candles to {DUCKDB_FILE} in table '{TABLE_NAME}'")
    if "interval_end" in candles[-1]:
        print(f"Last full candle interval_end: {candles[-1]['interval_end']}")


def consume_messages(batch_size=20):
    consumer = Consumer(
        {
            "bootstrap.servers": REDPANDA_BROKER,
            "group.id": "save-candle-group",
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([TOPIC])
    print("Subscribed to topic:", TOPIC)
    try:
        while True:
            messages = consumer.consume(num_messages=batch_size, timeout=1.0)
            if not messages:
                continue
            candles = []
            for msg in messages:
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        print("Kafka error:", msg.error())
                        continue
                try:
                    candle = json.loads(msg.value().decode("utf-8"))
                    candles.append(candle)
                except Exception as e:
                    print("Failed to decode message:", e)
            if candles:
                try:
                    save_to_duckdb(candles)
                    print(f"[✓] Saved {len(candles)} candles to DuckDB")
                    predict_and_save()
                except Exception as e:
                    print("Error saving to DuckDB:", e)
    finally:
        consumer.close()


if __name__ == "__main__":
    consume_messages()
