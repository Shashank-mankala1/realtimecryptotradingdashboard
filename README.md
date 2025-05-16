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
