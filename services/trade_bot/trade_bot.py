import logging
from datetime import datetime, timezone

import duckdb
import pandas as pd

# --- CONFIG ---
DUCKDB_FILE = "/data/crypto.duckdb"
STATE_TABLE = "tradebot_state"
PREDICTIONS_TABLE = "predictions"
START_BALANCE = 10000
STRATEGIES = ["dynamic", "balanced", "ultra_aggressive"]

logging.basicConfig(level=logging.INFO)


def get_last_state(conn):
    """
    Fetch the latest state for each strategy. Initialize if not present.
    """
    query = f"""
        SELECT *
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY strategy ORDER BY last_update DESC) as rn
            FROM {STATE_TABLE}
        )
        WHERE rn = 1
    """
    try:
        state_df = conn.execute(query).fetchdf()
        if state_df.empty:
            raise Exception("No state found")
        state = {row["strategy"]: row for _, row in state_df.iterrows()}
    except Exception:
        # Initialize state
        now = datetime.now(timezone.utc)
        state = {}
        for strat in STRATEGIES:
            state[strat] = {
                "strategy": strat,
                "balance": START_BALANCE,
                "position": 0.0,
                "last_price": 0.0,
                "last_update": now,
            }
        # Save initial state
        state_df = pd.DataFrame(state.values())
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {STATE_TABLE} (strategy VARCHAR, balance DOUBLE, position DOUBLE, last_price DOUBLE, last_update TIMESTAMP)"
        )
        conn.execute(f"INSERT INTO {STATE_TABLE} SELECT * FROM state_df")
    return state


def get_latest_prediction(conn):
    """
    Get the most recent prediction.
    """
    pred = conn.execute(
        f"SELECT * FROM {PREDICTIONS_TABLE} ORDER BY interval_start DESC LIMIT 1"
    ).fetchdf()
    if pred.empty:
        raise Exception("No predictions found")
    return pred.iloc[0]


def update_state(conn, state):
    """
    Append the updated state to DuckDB.
    """
    state_df = pd.DataFrame(state.values()).reset_index(drop=True)
    # Ensure columns are in the correct order and only the expected columns are present
    state_df = state_df[
        ["strategy", "balance", "position", "last_price", "last_update"]
    ]
    conn.execute(f"INSERT INTO {STATE_TABLE} SELECT * FROM state_df")


def trade_logic(strategy, state, price, signal, proba):
    """
    Simple buy/sell logic for each strategy.
    """
    balance = state["balance"]
    position = state["position"]
    if strategy == "dynamic":
        if signal == 1 and proba > 0.55 and balance > 0:
            position_size = balance * min(0.25 + (proba - 0.55), 0.5)
            units = position_size / price
            position += units
            balance -= position_size
        elif signal == 0 and position > 0:
            units_to_sell = position * 0.75
            balance += units_to_sell * price
            position -= units_to_sell
    elif strategy == "balanced":
        if signal == 1 and proba > 0.6 and balance > 0:
            position_size = balance * 0.25
            units = position_size / price
            position += units
            balance -= position_size
        elif signal == 0 and position > 0:
            units_to_sell = position * 0.75
            balance += units_to_sell * price
            position -= units_to_sell
    elif strategy == "ultra_aggressive":
        if signal == 1 and proba > 0.5 and balance > 0:
            position_size = min(balance * 0.5, balance)
            units = position_size / price
            position += units
            balance -= position_size
        elif signal == 0 and position > 0:
            units_to_sell = position * 0.5
            balance += units_to_sell * price
            position -= units_to_sell
    return balance, position


def main():
    with duckdb.connect(DUCKDB_FILE) as conn:
        # 1. Load or initialize state
        state = get_last_state(conn)
        # 2. Get latest prediction
        pred = get_latest_prediction(conn)
        # 3. Fetch the latest close price from candles
        candles = conn.execute(
            "SELECT * FROM candles ORDER BY interval_end DESC LIMIT 1"
        ).fetchdf()
        if candles.empty:
            raise Exception("No candle data found")
        price = candles["close"].iloc[0]
        signal = int(pred["signal"])
        proba = float(pred["proba"])
        now = datetime.now(timezone.utc)
        # 4. Update each strategy
        for strat in STRATEGIES:
            bal, pos = trade_logic(strat, state[strat], price, signal, proba)
            state[strat]["balance"] = bal
            state[strat]["position"] = pos
            state[strat]["last_price"] = price
            state[strat]["last_update"] = now
        # 5. Save updated state (append, not overwrite)
        update_state(conn, state)
        # 6. Print summary
        for strat in STRATEGIES:
            logging.info(
                f"{strat}: balance=${state[strat]['balance']:.2f}, position={state[strat]['position']:.6f} units, last_price={state[strat]['last_price']:.2f}"
            )


if __name__ == "__main__":
    # */5 * * * * sleep 30; /usr/local/bin/python /app/trade_bot.py >> /var/log/container.log 2>&1

    main()
