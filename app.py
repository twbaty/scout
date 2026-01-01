import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- APP CONFIGURATION ---
st.set_page_config(page_title="SCOUT | Intelligence Dashboard", layout="wide")

# Custom CSS for a sleek "Dark Mode" application look
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border-radius: 10px; padding: 15px; border: 1px solid #30363d; }
    </style>
    """, unsafe_base_config=True)

# --- DATABASE LOGIC ---
def get_stats():
    conn = sqlite3.connect("scout.db")
    # Total items in 90 days
    total = pd.read_sql_query("SELECT count(*) as count FROM items", conn).iloc[0]['count']
    # Newest items found in last 24 hours
    daily = pd.read_sql_query("SELECT count(*) as count FROM items WHERE found_date > datetime('now', '-1 day')", conn).iloc[0]['count']
    conn.close()
    return total, daily

# --- SIDEBAR (THE CONTROLS) ---
with st.sidebar:
    st.image("https://img.icons8.com/officel/80/shield.png", width=80)
    st.title("Scout Control")
    st.divider()
    search_query = st.text_input("Manual Intelligence Sweep:", placeholder="e.g. Texas Ranger Badge")
    run_button = st.button("🚀 Execute Search", use_container_width=True)
    st.divider()
    st.info("Agent Status: Active 🟢")

# --- MAIN DASHBOARD ---
st.title("🛡️ Scout Intelligence Terminal")

# 1. Top Level Metrics
col1, col2, col3 = st.columns(3)
total_finds, daily_finds = get_stats()

with col1:
    st.metric("90-Day Archive", total_finds)
with col2:
    st.metric("New (24h)", daily_finds, delta=f"{daily_finds} items")
with col3:
    st.metric("Next Roll-up", "Sunday")

# 2. Results Tabs
tab1, tab2 = st.tabs(["📊 Live Intelligence", "📜 90-Day History"])

with tab1:
    if run_button:
        st.write(f"Searching for **{search_query}**...")
        # Your scouting function would return 'results' here
        # st.dataframe(results, use_container_width=True)
    else:
        st.info("Enter a target in the sidebar to begin a live sweep.")

with tab2:
    conn = sqlite3.connect("scout.db")
    history_df = pd.read_sql_query("SELECT found_date as Date, target as Target, title as Item, price as Cost, url as Link FROM items ORDER BY found_date DESC", conn)
    conn.close()
    
    st.dataframe(history_df, 
                 column_config={"Link": st.column_config.Link_Column("View Listing")},
                 use_container_width=True, 
                 hide_index=True)
