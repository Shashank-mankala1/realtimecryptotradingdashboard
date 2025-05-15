import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone

from confluent_kafka import Producer
from websockets.sync.client import connect

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Constants
KRAKEN_WS_URL = "wss://ws.kraken.com/v2"
TRADING_PAIRS = ["BTC/USD"]
REDPANDA_BROKER = "redpanda-0:9092"  # Use 'localhost:19092' outside Docker
TOPIC = "crypto-trades"

# Kafka Producer
producer = Producer({"bootstrap.servers": REDPANDA_BROKER})

# Graceful shutdown flag
running = True


def delivery_report(err, msg):
    """Callback for Kafka delivery reports."""
    if err:
        logging.error(f"Delivery failed: {err}")
    else:
        logging.info(f"Delivered to {msg.topic()} [{msg.partition()}] @ {msg.offset()}")


def iso_to_unix_ms(timestamp_str):
    """Convert ISO 8601 string to Unix epoch in milliseconds."""
    dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def handle_shutdown(signum, frame):
    """Handle shutdown signals."""
    global running
    logging.info("Shutdown signal received. Exiting...")
    running = False


# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def stream_trades():
    """Stream trade data from Kraken WebSocket and produce to Redpanda."""
    subscription_msg = {
        "method": "subscribe",
        "params": {"channel": "trade", "symbol": TRADING_PAIRS},
    }

    MAX_RETRIES = 10
    RETRY_DELAY = 5  # seconds
    retries = 0

    while running:
        try:
            with connect(KRAKEN_WS_URL) as websocket:
                websocket.send(json.dumps(subscription_msg))
                logging.info(f"Subscribed to trades: {TRADING_PAIRS}")
                retries = 0  # Reset retries on successful connection

                last_ping = time.time()
                PING_INTERVAL = 30  # seconds

                while running:
                    if time.time() - last_ping > PING_INTERVAL:
                        try:
                            websocket.send(json.dumps({"method": "ping"}))
                            last_ping = time.time()
                        except Exception:
                            logging.exception("Ping failed, will reconnect.")
                            break  # Trigger reconnect

                    try:
                        message = websocket.recv()
                        data = json.loads(message)

                        if data.get("channel") in ("heartbeat", "status"):
                            continue

                        trades = data.get("data", [])
                        for trade in trades:
                            trade["timestamp_ms"] = iso_to_unix_ms(trade["timestamp"])
                            trade["timestamp"] = trade["timestamp"].replace("T", " ")
                            raw_symbol = trade.get("symbol")
                            symbol = raw_symbol.replace("/", "_")
                            trade["symbol"] = symbol

                            producer.produce(
                                topic=TOPIC,
                                key=symbol,
                                value=json.dumps(trade),
                                callback=delivery_report,
                            )

                        producer.poll(0)

                    except Exception:
                        logging.exception("Error processing message")
                        break  # Exit inner loop to reconnect

        except Exception:
            logging.exception("WebSocket connection failed")

        logging.info("Flushing producer...")
        producer.flush()

        if not running:
            break

        retries += 1
        if retries >= MAX_RETRIES:
            logging.error("Max retries exceeded. Exiting.")
            break

        logging.info(f"Reconnecting in {RETRY_DELAY} seconds... (attempt {retries})")
        time.sleep(RETRY_DELAY)


if __name__ == "__main__":
    stream_trades()
