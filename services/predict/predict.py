import json
from datetime import datetime, timedelta

import duckdb
import joblib
import numpy as np
import pandas as pd
import talib


# --- Feature engineering function (must match training) ---
def generate_features(
    candles,
    rolling_volatility_window=30,
    trix_period=30,
    tema_period=30,
    bbands_period=20,
    macd_fast=12,
    macd_slow=26,
    obv_window=30,
    ewma_span=10,
    predict_horizon_minutes=5,
):
    candles = candles.copy()

    candles["interval_start"] = pd.to_datetime(
        candles["interval_start"], format="mixed"
    )
    candles["interval_end"] = pd.to_datetime(candles["interval_end"], format="mixed")
    candles = candles.sort_values("interval_start").reset_index(drop=True)

    candles["future_close"] = candles["close"].shift(-predict_horizon_minutes)
    candles["target_return"] = (candles["future_close"] - candles["close"]) / candles[
        "close"
    ]
    candles["signal"] = (candles["target_return"] > 0).astype(int)

    candles["rolling_volatility"] = (
        candles["close"].rolling(window=rolling_volatility_window).std()
    )
    candles["volume_spike"] = (
        candles["volume"]
        / candles["volume"].rolling(window=rolling_volatility_window).mean()
    )
    candles["minute_of_day"] = (
        candles["interval_start"].dt.hour * 60 + candles["interval_start"].dt.minute
    )
    candles["momentum_5"] = candles["close"].pct_change(5)
    candles["momentum_15"] = candles["close"].pct_change(15)
    candles["range_ratio"] = (candles["high"] - candles["low"]) / candles["close"]
    candles["slope_10"] = candles["close"].diff(10) / 10
    candles["day_of_week"] = candles["interval_start"].dt.dayofweek
    candles["hour_sin"] = np.sin(2 * np.pi * candles["interval_start"].dt.hour / 24)
    candles["hour_cos"] = np.cos(2 * np.pi * candles["interval_start"].dt.hour / 24)

    us_market_open = 13
    asia_market_open = 1
    europe_market_open = 7

    def minutes_from_market(hour, minute, market_hour):
        mins = hour * 60 + minute
        delta = mins - market_hour * 60
        if delta < 0:
            delta += 1440
        return delta

    candles["minutes_from_us_open"] = candles["interval_start"].apply(
        lambda x: minutes_from_market(x.hour, x.minute, us_market_open)
    )
    candles["minutes_from_asia_open"] = candles["interval_start"].apply(
        lambda x: minutes_from_market(x.hour, x.minute, asia_market_open)
    )
    candles["minutes_from_europe_open"] = candles["interval_start"].apply(
        lambda x: minutes_from_market(x.hour, x.minute, europe_market_open)
    )

    for market in ["us", "asia", "europe"]:
        candles[f"norm_{market}_time"] = candles[f"minutes_from_{market}_open"] / 1440
        candles[f"{market}_time_sin"] = np.sin(
            2 * np.pi * candles[f"norm_{market}_time"]
        )
        candles[f"{market}_time_cos"] = np.cos(
            2 * np.pi * candles[f"norm_{market}_time"]
        )

    candles["trix"] = talib.TRIX(candles["close"].values, timeperiod=trix_period)
    candles["tema"] = talib.TEMA(candles["close"].values, timeperiod=tema_period)
    candles["dx"] = talib.DX(
        candles["high"].values,
        candles["low"].values,
        candles["close"].values,
    )
    candles["sar"] = talib.SAR(candles["high"].values, candles["low"].values)
    candles["atr"] = talib.ATR(
        candles["high"].values,
        candles["low"].values,
        candles["close"].values,
    )
    candles["volume_ema"] = candles["volume"].ewm(span=20).mean()
    candles["volume_ratio"] = candles["volume"] / candles["volume_ema"]
    candles["volume_oscillator"] = (
        candles["volume"].rolling(window=5).mean()
        / candles["volume"].rolling(window=20).mean()
        - 1
    ) * 100

    candles["vwap_daily"] = 0.0
    for date in candles["interval_start"].dt.date.unique():
        mask = candles["interval_start"].dt.date == date
        if mask.any():
            candles.loc[mask, "vwap_daily"] = (
                candles.loc[mask, "volume"] * candles.loc[mask, "close"]
            ).cumsum() / candles.loc[mask, "volume"].cumsum()
    candles["vwap_ratio"] = candles["close"] / candles["vwap_daily"].replace(0, np.nan)

    candles["adx"] = talib.ADX(
        candles["high"].values,
        candles["low"].values,
        candles["close"].values,
    )
    candles["adx_strong"] = (candles["adx"] > 25).astype(int)
    candles["obv"] = talib.OBV(candles["close"].values, candles["volume"].values)
    candles["obv_rolling"] = candles["obv"].rolling(window=obv_window).mean()
    candles["willr"] = talib.WILLR(
        candles["high"].values,
        candles["low"].values,
        candles["close"].values,
    )
    candles["mfi"] = talib.MFI(
        candles["high"].values,
        candles["low"].values,
        candles["close"].values,
        candles["volume"].values,
    )
    candles["rsi"] = talib.RSI(candles["close"].values)

    # EWMA features
    candles["ewma_close"] = candles["close"].ewm(span=ewma_span).mean()
    candles["ewma_volume"] = candles["volume"].ewm(span=ewma_span).mean()

    candles["macd"], candles["macd_signal"], candles["macd_hist"] = talib.MACD(
        candles["close"].values, fastperiod=macd_fast, slowperiod=macd_slow
    )

    for period in [5, 10, 20]:
        candles[f"direction_{period}"] = (
            np.sign(candles["close"].diff(period)).fillna(0).astype(int)
        )
        candles[f"sma_{period}"] = candles["close"].rolling(window=period).mean()
        candles[f"above_sma_{period}"] = (
            candles["close"] > candles[f"sma_{period}"]
        ).astype(int)

    sma_5 = candles["close"].rolling(window=5).mean()
    for period in [10, 20]:
        sma_period = candles["close"].rolling(window=period).mean()
        candles[f"ma_crossover_{period}"] = (
            (sma_5 > sma_period) & (sma_5.shift(1) <= sma_period.shift(1))
        ).astype(int)

    candles["bb_upper"], candles["bb_middle"], candles["bb_lower"] = talib.BBANDS(
        candles["close"].values, timeperiod=bbands_period
    )
    candles["bb_width"] = (candles["bb_upper"] - candles["bb_lower"]) / candles[
        "bb_middle"
    ]
    candles["bb_position"] = (candles["close"] - candles["bb_lower"]) / (
        candles["bb_upper"] - candles["bb_lower"]
    )
    candles["atr_ratio"] = candles["atr"] / candles["close"]

    for fast, slow in [(12, 26), (5, 35)]:
        macd, macd_signal, macd_hist = talib.MACD(
            candles["close"].values, fastperiod=fast, slowperiod=slow
        )
        candles[f"macd_{fast}_{slow}"] = macd
        candles[f"macd_signal_{fast}_{slow}"] = macd_signal
        candles[f"macd_hist_{fast}_{slow}"] = macd_hist
        candles[f"macd_cross_{fast}_{slow}"] = (
            (macd > macd_signal) & (np.roll(macd, 1) <= np.roll(macd_signal, 1))
        ).astype(int)

    candles["time_segment"] = pd.cut(
        candles["minute_of_day"],
        bins=[0, 360, 720, 1080, 1440],
        labels=["night", "morning", "afternoon", "evening"],
    )
    for segment in ["night", "morning", "afternoon", "evening"]:
        candles[f"time_{segment}"] = (candles["time_segment"] == segment).astype(int)

    candles["obv_trend"] = candles["obv"] * candles["adx"]
    candles["volume_volatility"] = (
        candles["volume_ratio"] * candles["rolling_volatility"]
    )
    candles["time_volume"] = candles["minute_of_day"] * candles["volume_ratio"]

    candles.fillna(candles.mean(numeric_only=True), inplace=True)
    return candles


# --- Prediction pipeline ---
def predict_and_save():
    duckdb_file = "/data/crypto.duckdb"
    candles_table = "candles"
    predictions_table = "predictions"
    model_path = "/data/models/latest.pkl"
    metrics_path = "/data/models/latest.json"

    # 1. Load model and feature params
    model = joblib.load(model_path)
    with open(metrics_path, "r") as f:
        best_params = json.load(f)["best_params"]

    # 2. Fetch last 30 days of candles
    now = datetime.utcnow()
    start_time = now - timedelta(days=30)
    query = f"""
        SELECT * FROM {candles_table}
        WHERE interval_start >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'
        ORDER BY interval_start
    """
    with duckdb.connect(duckdb_file) as conn:
        candles = conn.execute(query).fetchdf()

    # 3. Feature columns (must match training)
    feature_columns = [
        "rsi",
        "macd",
        "macd_signal",
        "macd_hist",
        "adx",
        "obv",
        "obv_rolling",
        "willr",
        "mfi",
        "trix",
        "tema",
        "dx",
        "sar",
        "atr",
        "rolling_volatility",
        "volume_spike",
        "minute_of_day",
        "momentum_5",
        "momentum_15",
        "range_ratio",
        "slope_10",
        "day_of_week",
        "hour_sin",
        "hour_cos",
        "minutes_from_us_open",
        "minutes_from_asia_open",
        "minutes_from_europe_open",
        "us_time_sin",
        "us_time_cos",
        "asia_time_sin",
        "asia_time_cos",
        "europe_time_sin",
        "europe_time_cos",
        "volume_ema",
        "volume_ratio",
        "volume_oscillator",
        "vwap_ratio",
        "adx_strong",
        "direction_5",
        "direction_10",
        "direction_20",
        "above_sma_5",
        "above_sma_10",
        "above_sma_20",
        "bb_width",
        "bb_position",
        "atr_ratio",
        "macd_12_26",
        "macd_signal_12_26",
        "macd_hist_12_26",
        "macd_5_35",
        "macd_signal_5_35",
        "macd_hist_5_35",
        "macd_cross_12_26",
        "macd_cross_5_35",
        "time_night",
        "time_morning",
        "time_afternoon",
        "time_evening",
        "obv_trend",
        "volume_volatility",
        "time_volume",
        "ewma_close",
        "ewma_volume",
    ]

    # 4. Generate features using best_params
    feature_param_keys = [
        "rolling_volatility_window",
        "trix_period",
        "tema_period",
        "bbands_period",
        "macd_fast",
        "macd_slow",
        "obv_window",
        "ewma_span",
    ]
    feature_params = {k: best_params[k] for k in feature_param_keys}
    candles = generate_features(candles, **feature_params, predict_horizon_minutes=5)

    # 5. Predict for the most recent candle
    latest_row = candles.iloc[[-1]]
    X_latest = latest_row[feature_columns]
    signal = int(model.predict(X_latest)[0])
    proba = float(model.predict_proba(X_latest)[0][1])
    interval_start = latest_row["interval_start"].iloc[0]
    interval_end = latest_row["interval_end"].iloc[0]

    # 6. Save prediction to DuckDB (create table if not exists)
    with duckdb.connect(duckdb_file) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS predictions (
                interval_start TIMESTAMP,
                interval_end TIMESTAMP,
                signal INTEGER,
                proba DOUBLE,
                PRIMARY KEY (interval_start, interval_end)
            )
        """
        )
        conn.execute(
            f"""
            INSERT INTO predictions (interval_start, interval_end, signal, proba)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(interval_start, interval_end) DO UPDATE SET
                signal=excluded.signal,
                proba=excluded.proba
        """,
            [interval_start, interval_end, signal, proba],
        )

    dt = pd.to_datetime(interval_start)
    prediction_time = dt + timedelta(minutes=5)

    print(
        f"Prediction saved: {interval_start} | signal={signal} | proba={proba:.4f} | 5 min ahead prediction at {prediction_time.strftime('%Y-%m-%d %H:%M:%S%z')}"
    )


if __name__ == "__main__":
    predict_and_save()
