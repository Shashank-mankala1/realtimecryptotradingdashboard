# Cryptocurrency TradeBots

## Steps 1: Start up the docker containers
1. Execute `docker build -t ml-trading-service ./services/base`
2. Execute `docker-compose up -d`

## Step 2: Fetch historical data from the past 30 days
1. Execute `docker exec -it backfill bash`
2. Execute `time python fetch_historical_trade_date.py`
3. Execute `time python load_historical_data_as_candles.py`

## Step 3: Start fetching the realtime crypto trades
1. Execute `docker exec -it realtime bash`
2. Execute `tmux`
3. Execute `python fetch_realtime_data.py`

## Step 4: Start candle-maker service
1. Execute `docker exec -it candle_maker bash`
2. Execute `tmux`
2. Execute `python candle_maker.py`


## Step 5: Start prediction service
1. Execute `docker exec -it predict bash`
2. Execute `tmux`
2. Execute `python process_candle.py`

## Step 6: Get gap data
1. Execute `docker exec -it backfill bash`
2. Execute `time python fetch_historical_trade_date.py` after update since last time stamp
3. Execute `time python load_historical_data_as_candles.py`

## Step 7: Setup Tradebot
1. Execute `docker exec -it trade_bot bash`
2. Execute `time python trade_bot.py`
3. Setup cronjob:
   1. crontab -e (quickly learn vim to add a line!)
   2. `*/5 * * * * sleep 30; /usr/local/bin/python /app/trade_bot.py >> /var/log/container.log 2>&1`

## Step 8: Setup Model training
1. Execute `docker exec -it train bash`
2. Execute `time python train.py`
3. Setup cronjob:
   1. crontab -e (quickly learn vim to add a line!)
   2. `50 * * * * sleep 30; /usr/local/bin/python /app/train.py > /var/log/container.log 2>&1`


## Step 9: Setup streamlit app
1. Execute `docker exec -it streamlit_app bash`
2. Execute `tmux`
2. Execute `streamlit run streamlit_app.py`


## TMUX

- **List sessions:**
  `tmux ls`

- **Attach to session:**
  `tmux attach -t <session-name>`

- **Detach:**
  Press `Ctrl+b`, then `d`


## VIM

- **Enter edit mode:**
  Press `i`

- **Paste (in insert mode):**
  Use your terminal's paste (e.g., `Ctrl+Shift+V` or right-click paste)

- **Save and exit:**
  Press `Esc`, then type `:wq` and press `Enter`



## Grading Rubric

| Points | Requirement                            | How It Will Be Graded                                                                                    |
| ------ | -------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 30     | crypto-trades topic                    | Grader will ask you to show new trades.                                                                  |
| 30     | crypto-candles topic                   | Grader will ask you to show new candles.                                                                 |
| 30     | Run `last_predictions`                 | Grader will ask you to run the file and print the last 20 predictions.                                   |
| 30     | 12 trained models in data folder       | Grader will ask you to show the folder (SSH into the box using VS Code and display the folder contents). |
| 30     | Streamlit app shows 30 days of candles | Grader will inspect your Streamlit app to verify it displays 30 days worth of candle data.               |
| 30     | 12 hours worth of trading              | Grader will inspect your Streamlit app for at least 12 hours of trading data.                            |
| 20     | 24 hours worth of trading              | Grader will inspect your Streamlit app for at least 24 hours of trading data.                            |
| 10     | 48 hours worth of trading              | Grader will inspect your Streamlit app for at least 48 hours of trading data.                            |
| 5      | 72 hours worth of trading              | Grader will inspect your Streamlit app for at least 72 hours of trading data.                            |
| 30     | public streamlit app                   | Grader will inspect your Streamlit app                                                              s    |


## Feature Information

| Feature Name             | Description / What It Does                                      | Window/Range (Minutes) | Optuna Tuned?    | Notes (1-min Candle Context) |
| ------------------------ | --------------------------------------------------------------- | ---------------------- | ---------------- | ---------------------------- |
| above_sma_10             | 1 if close > 10-min SMA, else 0                                 | 10                     | No               | 10 min SMA                   |
| above_sma_20             | 1 if close > 20-min SMA, else 0                                 | 20                     | No               | 20 min SMA                   |
| above_sma_5              | 1 if close > 5-min SMA, else 0                                  | 5                      | No               | 5 min SMA                    |
| adx                      | Average Directional Index, trend strength indicator             | 14 (TA-Lib default)    | No               | 14-min ADX                   |
| adx_strong               | 1 if ADX > 25, else 0 (trend strength flag)                     | 14                     | No               | 14-min ADX                   |
| asia_time_cos            | Cosine encoding of normalized Asia market time                  | 0–1                    | No               | -                            |
| asia_time_sin            | Sine encoding of normalized Asia market time                    | 0–1                    | No               | -                            |
| atr                      | Average True Range, measures volatility                         | 14 (TA-Lib default)    | No               | 14-min window                |
| atr_ratio                | ATR divided by close price                                      | 14                     | No               | 14-min ATR                   |
| bb_position              | (Close - lower BB) / (upper BB - lower BB)                      | 10–40                  | Yes (10–40)      | 10–40 min window             |
| bb_width                 | Bollinger Band width (upper - lower) / middle                   | 10–40                  | Yes (10–40)      | 10–40 min window             |
| day_of_week              | Day of week (0=Monday, 6=Sunday)                                | 0–6                    | No               | -                            |
| direction_10             | Sign of 10-min price change                                     | 10                     | No               | 10 min direction             |
| direction_20             | Sign of 20-min price change                                     | 20                     | No               | 20 min direction             |
| direction_5              | Sign of 5-min price change                                      | 5                      | No               | 5 min direction              |
| dx                       | Directional Movement Index, trend strength                      | 14 (TA-Lib default)    | No               | 14-min window                |
| ewma_close               | Exponential weighted moving average of close price              | 3–40                   | Yes (3–40)       | 3–40 min smoothing           |
| ewma_volume              | Exponential weighted moving average of volume                   | 3–40                   | Yes (3–40)       | 3–40 min smoothing           |
| hour_cos                 | Cosine encoding of hour of day                                  | 0–23                   | No               | -                            |
| hour_sin                 | Sine encoding of hour of day                                    | 0–23                   | No               | -                            |
| macd                     | MACD line: fast EMA - slow EMA                                  | fast/slow tunable      | Yes (1–19, 2–40) | Fast/slow EMA in minutes     |
| macd_12_26               | MACD line with fast=12, slow=26                                 | 12, 26                 | No               | Standard MACD                |
| macd_5_35                | MACD line with fast=5, slow=35                                  | 5, 35                  | No               | Variant MACD                 |
| macd_cross_12_26         | 1 if MACD_12_26 crosses above its signal, else 0                | 12, 26                 | No               | Standard MACD                |
| macd_cross_5_35          | 1 if MACD_5_35 crosses above its signal, else 0                 | 5, 35                  | No               | Variant MACD                 |
| macd_hist                | MACD histogram: macd - macd_signal                              | Derived                | No               | -                            |
| macd_hist_12_26          | Histogram for MACD_12_26                                        | Derived                | No               | -                            |
| macd_hist_5_35           | Histogram for MACD_5_35                                         | Derived                | No               | -                            |
| macd_signal              | Signal line: EMA of MACD line                                   | 9 (TA-Lib default)     | No               | 9-min EMA of MACD            |
| macd_signal_12_26        | Signal line for MACD_12_26                                      | 9                      | No               | Standard MACD                |
| macd_signal_5_35         | Signal line for MACD_5_35                                       | 9                      | No               | Variant MACD                 |
| mfi                      | Money Flow Index, volume-weighted RSI                           | 14 (TA-Lib default)    | No               | 14-min window                |
| minute_of_day            | Minutes since midnight (0-1439)                                 | 0–1439                 | No               | -                            |
| minutes_from_asia_open   | Minutes since Asia market open (01:00 UTC)                      | 0–1439                 | No               | -                            |
| minutes_from_europe_open | Minutes since Europe market open (07:00 UTC)                    | 0–1439                 | No               | -                            |
| minutes_from_us_open     | Minutes since US market open (13:00 UTC)                        | 0–1439                 | No               | -                            |
| momentum_15              | 15-period percent change in close price                         | 15                     | No               | 15 min momentum              |
| momentum_5               | 5-period percent change in close price                          | 5                      | No               | 5 min momentum               |
| obv                      | On-Balance Volume, cumulative volume flow                       | All data               | No               | Cumulative                   |
| obv_rolling              | Rolling mean of OBV                                             | 5–60                   | Yes (5–60)       | 5–60 min average             |
| obv_trend                | OBV multiplied by ADX (volume trend weighted by trend strength) | Derived                | No               | -                            |
| range_ratio              | (High - Low) / Close, measures daily range relative to price    | 1                      | No               | Current bar                  |
| rolling_volatility       | Rolling std dev of close price (volatility)                     | 10–60                  | Yes (10–60)      | 10–60 min window             |
| rsi                      | Relative Strength Index, momentum oscillator                    | 14 (TA-Lib default)    | No               | 14-min RSI                   |
| sar                      | Parabolic SAR, trend-following stop and reverse                 | N/A                    | No               | -                            |
| slope_10                 | Slope of close price over 10 periods                            | 10                     | No               | 10 min slope                 |
| tema                     | Triple Exponential Moving Average                               | 10–70                  | Yes (10–70)      | 10–70 min smoothing          |
| time_afternoon           | 1 if time segment is afternoon (12:00–18:00 UTC), else 0        | 720–1080               | No               | -                            |
| time_evening             | 1 if time segment is evening (18:00–24:00 UTC), else 0          | 1080–1440              | No               | -                            |
| time_morning             | 1 if time segment is morning (06:00–12:00 UTC), else 0          | 360–720                | No               | -                            |
| time_night               | 1 if time segment is night (00:00–06:00 UTC), else 0            | 0–360                  | No               | -                            |
| time_volume              | minute_of_day multiplied by volume_ratio                        | 20                     | No               | 20 min EMA                   |
| trix                     | TRIX, triple-smoothed EMA rate of change                        | 10–70                  | Yes (10–70)      | 10–70 min smoothing          |
| us_time_cos              | Cosine encoding of normalized US market time                    | 0–1                    | No               | -                            |
| us_time_sin              | Sine encoding of normalized US market time                      | 0–1                    | No               | -                            |
| volume_ema               | Exponential moving average of volume                            | 20                     | No               | 20 min EMA                   |
| volume_oscillator        | (5-min MA of volume / 20-min MA of volume) - 1, as %            | 5, 20                  | No               | 5 and 20 min averages        |
| volume_ratio             | Volume divided by volume_ema                                    | 20                     | No               | 20 min EMA                   |
| volume_spike             | Volume divided by rolling mean volume                           | 10–60                  | Yes (10–60)      | Same as rolling_volatility   |
| volume_volatility        | volume_ratio multiplied by rolling_volatility                   | 10–60                  | Yes (10–60)      | 10–60 min window             |
| vwap_ratio               | Close price divided by daily VWAP                               | 1 day                  | No               | -                            |
| willr                    | Williams %R, overbought/oversold indicator                      | 14 (TA-Lib default)    | No               | 14-min window                |