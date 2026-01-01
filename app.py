import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

# Custom Styling
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 2rem; color: #58a6ff; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE ENGINE ---
def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    # Items Table
    conn.execute('''CREATE TABLE IF NOT EXISTS items 
                 (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  target TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    # Saved Targets Table
    conn.execute('''CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

# --- 3. MOCK SCRAPER (With Real URL Logic) ---
def perform_scout_sweep(query):
    time.sleep(1) 
    # Generating unique IDs to simulate real eBay listings
    ts = int(time.time())
    return [
        {"target": query, "title": f"{query} - Premium Grade", "price": "$299.00", "url": f"https://www.ebay.com/itm/{ts}1"},
        {"target": query, "title": f"Vintage {query} LEO", "price": "$450.00", "url": f"https://www.ebay.com/itm/{ts}2"}
    ]

# --- 4. SIDEBAR: THE SEARCH LIBRARY ---
init_db()
with st.sidebar:
    st.title("🛡️ Scout Control")
    
    # Target Management
    st.subheader("Search Library")
    new_target = st.text_input("Add New Target:", placeholder="e.g. OHP Oval Patch")
    if st.button("➕ Add to Library"):
        if new_target:
            conn = get_db_connection()
            try:
                conn.execute("INSERT INTO targets (name) VALUES (?)", (new_target,))
                conn.commit()
            except: pass
            conn.close()

    # Show Current Library
    conn = get_db_connection()
    current_targets = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
    conn.close()
    
    if current_targets:
        target_to_del = st.selectbox("Current Library:", current_targets)
        if st.button("🗑️ Remove Selected"):
            conn = get_db_connection()
            conn.execute("DELETE FROM targets WHERE name = ?", (target_to_del,))
            conn.commit()
            conn.close()
            st.rerun()
    
    st.divider()
    run_all = st.button("🚀 Run Library Sweep", use_container_width=True)

# --- 5. MAIN DASHBOARD ---
st.title("Scout Intelligence Terminal")

# Metrics Logic
conn = get_db_connection()
total_count = pd.read_sql_query("SELECT count(*) as count FROM items", conn).iloc[0]['count']
new_today = pd.read_sql_query("SELECT count(*) as count FROM items WHERE found_date > datetime('now', '-1 day')", conn).iloc[0]['count']
conn.close()

m_col1, m_col2, m_col3 = st.columns(3)
m_col1.metric("90-Day Archive", total_count)
m_col2.metric("New Finds (Today)", new_today)
m_col3.metric("System Status", "Ready")

tab1, tab2 = st.tabs(["📊 Live Sweep", "📜 Intelligence History"])

with tab1:
    if run_all:
        if not current_targets:
            st.warning("Your Library is empty. Add a target in the sidebar first.")
        else:
            all_results = []
            with st.status("Executing Library Sweep...", expanded=True) as status:
                for target in current_targets:
                    st.write(f"Scouting: {target}")
                    found = perform_scout_sweep(target)
                    
                    conn = get_db_connection()
                    for item in found:
                        try:
                            conn.execute("INSERT INTO items (target, title, price, url) VALUES (?, ?, ?, ?)",
                                         (item['target'], item['title'], item['price'], item['url']))
                            all_results.append(item)
                        except sqlite3.IntegrityError: pass
                    conn.commit()
                    conn.close()
                status.update(label="✅ Sweep Complete!", state="complete")
            
            st.success(f"Sweep finished. Found {len(all_results)} total items.")
            # Force refresh to update the "New Finds" metric at the top
            st.button("Click to Update Dashboard Metrics") 

with tab2:
    conn = get_db_connection()
    history_df = pd.read_sql_query("SELECT found_date as Date, target as Target, title as Item, price as Cost, url as Link FROM items ORDER BY found_date DESC", conn)
    conn.close()

    st.dataframe(
        history_df,
        column_config={"Link": st.column_config.LinkColumn("View Listing")},
        use_container_width=True, hide_index=True
    )
