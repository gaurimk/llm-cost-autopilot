"""
Cost & Quality Dashboard
==========================
A Streamlit dashboard reading directly from the SQLite audit log. Shows:
  - Total cost vs. what it would have cost using the reference model for
    everything ("you saved $X" -- the headline portfolio metric)
  - Routing distribution (which models handle what % of traffic)
  - Quality score distribution from the verifier
  - Escalation rate over time

Run with:  streamlit run app/dashboard/streamlit_app.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "autopilot.db"

st.set_page_config(page_title="LLM Cost Autopilot Dashboard", layout="wide")
st.title("LLM Cost Autopilot -- Cost & Quality Dashboard")


@st.cache_data(ttl=15)
def load_data() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM requests", conn)
    conn.close()
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df["date"] = df["timestamp"].dt.date
    return df


df = load_data()

if df.empty:
    st.info(
        "No requests logged yet. Send some traffic to POST /v1/completions "
        "(or run scripts/load_test.py) and refresh this page."
    )
    st.stop()

# --- Headline metric ---------------------------------------------------
total_cost = df["cost"].sum()
reference_cost = df["reference_cost"].sum()
savings_pct = ((reference_cost - total_cost) / reference_cost * 100) if reference_cost > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total requests", len(df))
col2.metric("Actual cost", f"${total_cost:,.4f}")
col3.metric("Cost if all on reference model", f"${reference_cost:,.4f}")
col4.metric("Cost saved", f"{savings_pct:.1f}%", delta=f"-${reference_cost - total_cost:,.4f}")

st.divider()

# --- Cost over time ------------------------------------------------------
st.subheader("Cost per day: actual vs. reference-model baseline")
daily = df.groupby("date")[["cost", "reference_cost"]].sum().rename(
    columns={"cost": "Actual cost", "reference_cost": "If routed to reference model"}
)
st.line_chart(daily)

# --- Routing distribution -------------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader("Routing distribution")
    dist = df["routed_model"].value_counts()
    st.bar_chart(dist)

with right:
    st.subheader("Quality score distribution")
    if df["quality_score"].notna().any():
        st.bar_chart(df["quality_score"].dropna())
    else:
        st.caption("No quality scores yet -- the async verifier hasn't scored any requests.")

# --- Escalation rate over time --------------------------------------------
st.subheader("Escalation rate over time")
esc_daily = df.groupby("date")["escalated"].mean() * 100
st.line_chart(esc_daily.rename("Escalation rate (%)"))

st.subheader("Raw request log (most recent 100)")
st.dataframe(df.sort_values("timestamp", ascending=False).head(100), use_container_width=True)
