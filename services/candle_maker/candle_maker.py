import logging
import os
from datetime import datetime, timedelta

from quixstreams import Application
from quixstreams.models import TopicConfig

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ENVIRONMENT TOGGLE
ENV = os.getenv("ENV", "dev").lower()  # Can be 'dev' or 'prod'

# Configuration
REDPANDA_BROKER = "redpanda-0:9092"
TRADE_TOPIC = "crypto-trades"
CANDLE_TOPIC = "crypto-candles"
CANDLE_INTERVAL_SECONDS = 60
BUFFER_PERIOD_SECONDS = 5

# Define dev and prod configs
env_config = {
    "dev": {"replication_factor": 1, "num_partitions": 1},
    "prod": {"replication_factor": 3, "num_partitions": 6},
}

# Select config based on environment
trade_topic_config = TopicConfig(**env_config[ENV])
candle_topic_config = TopicConfig(**env_config[ENV])


def process_trade(trade, state):
    try:
        # Get existing candles from state or initialize empty dict
        candles = state.get("candles", default={})

        # Get the last processed timestamp
        last_processed_time = state.get("last_processed_time", default=None)

        # Parse trade data
        symbol = trade["symbol"]
        price = float(trade["price"])
        qty = float(trade["qty"])
        timestamp = datetime.fromisoformat(trade["timestamp"])

        # Calculate interval start time (floor to nearest minute)
        interval_start = timestamp.replace(second=0, microsecond=0)

        # Calculate interval end time
        interval_end = interval_start + timedelta(seconds=CANDLE_INTERVAL_SECONDS)

        # Create composite key (symbol_timestamp)
        key = f"{symbol}_{interval_start.isoformat()}"

        # Update or create candle
        if key not in candles:
            candles[key] = {
                "symbol": symbol,
                "interval_start": interval_start.strftime("%Y-%m-%d %H:%M:%S%z"),
                "interval_end": interval_end.strftime("%Y-%m-%d %H:%M:%S%z"),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": qty,
                "trade_count": 1,
            }
        else:
            c = candles[key]
            c["high"] = max(c["high"], price)
            c["low"] = min(c["low"], price)
            c["close"] = price
            c["volume"] += qty
            c["trade_count"] = c.get("trade_count", 0) + 1

        # Save updated candles back to state
        state.set("candles", candles)

        # Update last processed time if this trade is newer
        if last_processed_time is None or timestamp.isoformat() > last_processed_time:
            state.set("last_processed_time", timestamp.isoformat())

        # Find candles to emit based on the current trade's timestamp
        # A candle is complete if:
        # 1. Its interval end time is in the past relative to the current trade
        # 2. We've seen trades that are at least BUFFER_PERIOD_SECONDS newer than its end time
        candle_to_emit = None

        # Only attempt to emit candles if we've moved forward in time significantly
        if last_processed_time is not None:
            last_time = datetime.fromisoformat(last_processed_time)
            time_jump = (timestamp - last_time).total_seconds()

            # If we've jumped forward in time by more than the buffer period,
            # check for candles that can be emitted
            if time_jump > BUFFER_PERIOD_SECONDS:
                completed_candles = []

                for key, candle in list(candles.items()):
                    candle_end = datetime.fromisoformat(candle["interval_end"])

                    # If the current trade is more than buffer period after the candle's end,
                    # the candle is complete
                    if timestamp >= candle_end + timedelta(
                        seconds=BUFFER_PERIOD_SECONDS
                    ):
                        completed_candles.append((key, candle.copy()))

                # Sort by interval start time and get the oldest
                if completed_candles:
                    completed_candles.sort(key=lambda x: x[1]["interval_start"])
                    oldest_key, oldest_candle = completed_candles[0]

                    # Remove the emitted candle
                    del candles[oldest_key]
                    state.set("candles", candles)

                    logger.info(
                        f"Emitting candle for {oldest_candle['symbol']} from {oldest_candle['interval_start']} to {oldest_candle['interval_end']} (trades: {oldest_candle.get('trade_count', 'unknown')})"
                    )
                    candle_to_emit = oldest_candle

        return candle_to_emit

    except Exception as e:
        logger.error(f"Error processing trade: {e}", exc_info=True)
        return None


def log_trade(trade, state):
    logger.info(f"Received trade for {trade['symbol']}")
    return trade


# Create the Quix app
app = Application(
    broker_address=REDPANDA_BROKER,
    consumer_group="candle-generator-group",
    auto_offset_reset="earliest",
    auto_create_topics=True,
)

# Define input and output topics with selected config
trade_topic = app.topic(
    name=TRADE_TOPIC,
    key_deserializer="string",
    value_deserializer="json",
    config=trade_topic_config,
)

candle_topic = app.topic(
    name=CANDLE_TOPIC, value_serializer="json", config=candle_topic_config
)

# Define the stream
sdf = app.dataframe(topic=trade_topic)

sdf = sdf.apply(log_trade, stateful=True)

sdf = (
    sdf.apply(process_trade, stateful=True)
    .filter(lambda candle: candle is not None)  # Filter out None values
    .update(lambda candle: logger.info(f"Emitted candle: {candle}"))
    .to_topic(candle_topic)
)

if __name__ == "__main__":
    logger.info(f"Running in {ENV.upper()} mode")
    app.clear_state()
    app.run()
