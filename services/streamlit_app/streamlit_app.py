import json
import os
import time

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()
PASSWORD = os.getenv(
    "STREAMLIT_PASSWORD", "Donation-Ladybug-Glucose-Amulet-Satchel5"
)  # Default fallback

# --- CONFIG ---
DUCKDB_FILE = "/data/crypto.duckdb"
CANDLES_TABLE = "candles"
STATE_TABLE = "tradebot_state"
MODEL_METRICS_PATH = "/data/models/latest.json"
STRATEGIES = ["dynamic", "balanced", "ultra_aggressive"]
STRATEGY_LABELS = {
    "dynamic": "Dynamic",
    "balanced": "Balanced",
    "ultra_aggressive": "Ultra Aggressive",
}
STRATEGY_ICONS = {"dynamic": "⚡", "balanced": "⚖️", "ultra_aggressive": "🔥"}


# --- PASSWORD PROTECTION ---
def password_protect():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if not st.session_state["authenticated"]:
        st.title("Crypto Dashboard Login")
        pw = st.text_input("Enter password:", type="password")
        if st.button("Login"):
            if pw == PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()


password_protect()


# --- HELPER FUNCTIONS ---
def get_candles(n=200):
    with duckdb.connect(DUCKDB_FILE) as conn:
        df = conn.execute(
            f"SELECT * FROM {CANDLES_TABLE} ORDER BY interval_start DESC LIMIT {n}"
        ).fetchdf()
    df = df.sort_values("interval_start")
    return df


def get_tradebot_state():
    with duckdb.connect(DUCKDB_FILE) as conn:
        df = conn.execute(f"SELECT * FROM {STATE_TABLE}").fetchdf()
    return df


def get_model_metrics():
    try:
        with open(MODEL_METRICS_PATH, "r") as f:
            metrics = json.load(f)
        return metrics
    except Exception:
        return None


def plot_candles(df):
    if df.empty:
        st.info("No candle data available.")
        return

    df["interval_start"] = pd.to_datetime(df["interval_start"])
    x_max = df["interval_start"].max()
    x_min_candidate = x_max - pd.Timedelta(hours=12)
    x_min = max(df["interval_start"].min(), x_min_candidate)

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df["interval_start"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                increasing_line_color="green",
                decreasing_line_color="red",
            )
        ]
    )
    fig.update_layout(
        title="Latest Candle Data",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis=dict(range=[x_min, x_max]),
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_balances(state_df):
    st.subheader("Strategy Total Value")
    cols = st.columns(3)
    for i, strat in enumerate(STRATEGIES):
        strat_row = state_df[state_df["strategy"] == strat]
        if not strat_row.empty:
            latest = strat_row.sort_values("last_update", ascending=False).iloc[0]
            bal = latest["balance"]
            pos = latest["position"]
            price = latest["last_price"]
            total_value = bal + pos * price
            cols[i].metric(
                f"{STRATEGY_ICONS[strat]} {STRATEGY_LABELS[strat]}",
                f"${total_value:,.2f}",
                f"{pos:.4f} units",
            )
        else:
            cols[i].metric(
                f"{STRATEGY_ICONS[strat]} {STRATEGY_LABELS[strat]}", "N/A", "N/A"
            )


def plot_balance_history():
    st.subheader("Strategy Total Value History")
    with duckdb.connect(DUCKDB_FILE) as conn:
        df = conn.execute(f"SELECT * FROM {STATE_TABLE} ORDER BY last_update").fetchdf()
    if df.empty:
        st.info("No balance history available.")
        return
    import plotly.express as px

    df["last_update"] = pd.to_datetime(df["last_update"])
    df["total_value"] = df["balance"] + df["position"] * df["last_price"]

    fig = px.line(
        df,
        x="last_update",
        y="total_value",
        color="strategy",
        markers=True,
        labels={
            "last_update": "Time",
            "total_value": "Total Value ($)",
            "strategy": "Strategy",
        },
        title="Strategy Total Value Over Time",
        color_discrete_map={
            "dynamic": "#636EFA",
            "balanced": "#00CC96",
            "ultra_aggressive": "#EF553B",
        },
    )
    fig.add_hline(
        y=10000,
        line_dash="dash",
        line_color="gray",
        annotation_text="Starting Balance ($10,000)",
        annotation_position="top left",
    )
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    # Display latest predictions
    st.subheader("Latest Predictions")
    try:
        with duckdb.connect(DUCKDB_FILE) as conn:
            query = """
                SELECT *
                FROM predictions
                ORDER BY interval_start DESC
                LIMIT 20
            """
            pred_df = conn.execute(query).fetchdf()

        if not pred_df.empty:
            st.dataframe(pred_df)
        else:
            st.info("No predictions available.")
    except Exception as e:
        st.error(f"Failed to load predictions: {e}")


# --- MAIN APP ---
st.set_page_config(
    page_title="Crypto Trading Dashboard", page_icon=":bar_chart:", layout="wide"
)
st.title("Crypto Trading Dashboard")

# --- Model Info Card ---
metrics = get_model_metrics()
if metrics:
    with st.container():
        st.markdown(
            f"""
            <div style="background-color:#f0f2f6;padding:1em 2em;border-radius:10px;display:flex;align-items:center;box-shadow:0 2px 8px #e0e0e0;">
                <span style="font-size:2em;margin-right:1em;">🤖</span>
                <div>
                    <b>Latest Model:</b> <code>{metrics['timestamp']}</code><br>
                    <b>F1 Score:</b> <span style="color:green;font-weight:bold;">{metrics['f1_score']}</span><br>
                    <b>Accuracy:</b> {metrics['accuracy']}<br>
                    <b>Precision:</b> {metrics['precision']}<br>
                    <b>Recall:</b> {metrics['recall']}<br>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# --- Tabs ---
tab1, tab2 = st.tabs(["Candle Data", "Strategy Balances"])

# --- Tab 1: Candle Data ---
with tab1:
    st.header("Candle Data")
    manual_refresh = st.button("Manual Refresh")
    last_refresh = st.session_state.get("last_candle_refresh", 0)
    now = time.time()
    if manual_refresh or now - last_refresh > 60:
        candle_df = get_candles(200)
        st.session_state["last_candle_refresh"] = now
    else:
        candle_df = get_candles(200)
    plot_candles(candle_df)
    st.info(
        "Data auto-refreshes every 1 minute. Click manual refresh for instant update."
    )

with tab2:
    st.header("Strategy Balances")

    # Refresh logic
    manual_refresh2 = st.button("Manual Refresh", key="refresh2")
    last_refresh2 = st.session_state.get("last_balance_refresh", 0)
    now2 = time.time()
    if manual_refresh2 or now2 - last_refresh2 > 300:
        state_df = get_tradebot_state()
        st.session_state["last_balance_refresh"] = now2
    else:
        state_df = get_tradebot_state()

    # Plots and info
    plot_balances(state_df)
    plot_balance_history()
    st.info(
        "Data auto-refreshes every 5 minutes. Click manual refresh for instant update."
    )


# --- Footer ---
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:gray;font-size:0.95em;'>"
    "Powered by your AI trading assistant."
    "</div>",
    unsafe_allow_html=True,
)
