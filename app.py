import streamlit as st
import pandas as pd
import sqlite3
import os
import logging
import requests
import time
from datetime import datetime

# --- 1. CORE SYSTEM CONFIG ---
st.set_page_config(page_title="SCOUT | Terminal", layout="wide")

# CSS: Sticky Tabs & UI Polish
st.markdown("""
    <style>
    div[data-testid="stTabs"] {
        position: fixed;
        top: 0;
        z-index: 1000;
        background-color: #f0f2f6;
        padding-top: 10px;
    }
    .stApp { margin-top: 60px; }
    </style>
    """, unsafe_allow_html=True)

# API Setup
try:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
except:
    st.error("Missing API Key in .streamlit/secrets.toml")
    st.stop()

LOG_FILE = 'scout.log'
def setup_logger():
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

logger = setup_logger()

# --- 2. DATABASE ---
def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY, frequency TEXT DEFAULT "Manual", last_run TIMESTAMP)')
    conn.commit(); conn.close()

init_db()

# --- 3. THE FIXED SCOUTING LOGIC ---
def run_scout_mission(query, engine):
    url = "https://serpapi.com/search.json"
    params = {"api_key": SERP_API_KEY, "engine": engine}
    
    # Engine-specific parameter mapping
    if engine == "ebay": params["_nkw"] = query
    else: params["q"] = query

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        # KEY FIX: Mapping the correct JSON keys based on your provided data
        raw_items = []
        if engine == "ebay":
            raw_items = data.get("ebay_results", [])
        elif engine == "etsy":
            raw_items = data.get("etsy_results", [])
        elif engine == "google_shopping":
            raw_items = data.get("shopping_results", [])

        # If SerpApi sends an error string instead of a list
        if isinstance(raw_items, str) or raw_items is None:
            logger.error(f"Engine {engine} returned no list. check API credits or query.")
            return []

        results = []
        for i in raw_items[:20]:
            # Handle different price structures across platforms
            price_val = "N/A"
            if isinstance(i.get("price"), dict):
                price_val = i.get("price", {}).get("raw", "N/A")
            else:
                price_val = i.get("price", "N/A")

            results.append({
                "target": query,
                "source": engine.replace("_", " ").capitalize(),
                "title": i.get("title", "No Title"),
                "price": price_val,
                "url": i.get("link", i.get("product_link", "#"))
            })
        return results
    except Exception as e:
        logger.error(f"Failure on {engine}: {str(e)}")
        return []

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ SCOUT")
    conn = get_db_connection()
    targets_df = pd.read_sql_query("SELECT name FROM targets", conn)
    conn.close()
    
    st.write("### Active Targets")
    selected_targets = [t for t in targets_df['name'] if st.checkbox(t, value=True, key=f"sb_{t}")]
    
    st.divider()
    run_mission = st.button("🚀 START SWEEP", use_container_width=True, type="primary")

# --- 5. TABS ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs(["📡 Live", "📊 Dashboard", "📜 Archive", "⚙️ Config", "🛠️ Logs"])

with t_live:
    if run_mission and selected_targets:
        all_hits = []
        progress_bar = st.progress(0)
        
        for idx, target in enumerate(selected_targets):
            st.write(f"🔍 Scanning for: **{target}**")
            
            # Run the 3 engines
            if st.session_state.get('p_ebay', True): all_hits.extend(run_scout_mission(target, "ebay"))
            if st.session_state.get('p_etsy', True): all_hits.extend(run_scout_mission(target, "etsy"))
            if st.session_state.get('p_google', True): all_hits.extend(run_scout_mission(target, "google_shopping"))
            
            # Update DB timestamp
            conn = get_db_connection()
            conn.execute("UPDATE targets SET last_run = ? WHERE name = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), target))
            conn.commit(); conn.close()
            
            progress_bar.progress((idx + 1) / len(selected_targets))
            time.sleep(1) # Be nice to the API
        
        # Save results
        conn = get_db_connection()
        for h in all_hits:
            try: conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?, ?, ?, ?, ?)", (h['target'], h['source'], h['title'], h['price'], h['url']))
            except: pass # Skip duplicates
        conn.commit(); conn.close()
        st.session_state['last_results'] = all_hits
        st.success(f"Sweep Finished. {len(all_hits)} items found.")

    if st.session_state.get('last_results'):
        st.dataframe(pd.DataFrame(st.session_state['last_results']), use_container_width=True, hide_index=True)

with t_dash:
    conn = get_db_connection()
    df_all = pd.read_sql_query("SELECT source, target FROM items", conn)
    conn.close()
    if not df_all.empty:
        st.subheader("🎯 Source Discovery Heatmap")
        heatmap = df_all.groupby(['target', 'source']).size().unstack(fill_value=0)
        st.table(heatmap)

with t_arch:
    st.header("Intelligence Archive")
    c1, c2 = st.columns([4, 1])
    with c2:
        depth = st.selectbox("View Depth:", [50, 100, 500, "All"], index=0)
    
    limit = "" if depth == "All" else f"LIMIT {depth}"
    conn = get_db_connection()
    arch_df = pd.read_sql_query(f"SELECT found_date, source, target, title, price, url FROM items ORDER BY found_date DESC {limit}", conn)
    conn.close()
    
    st.dataframe(arch_df, column_config={"url": st.column_config.LinkColumn("Link")}, use_container_width=True, hide_index=True, height=600)

with t_conf:
    st.header("Configuration")
    st.subheader("Marketplace Access")
    col1, col2, col3 = st.columns(3)
    col1.toggle("eBay", value=True, key="p_ebay")
    col2.toggle("Etsy", value=True, key="p_etsy")
    col3.toggle("Google Shopping", value=True, key="p_google")
    
    st.divider()
    st.subheader("Add New Search Keyword")
    with st.form("add_keyword"):
        k_name = st.text_input("Keyword:")
        k_freq = st.selectbox("Frequency:", ["Manual", "Daily", "Weekly"])
        if st.form_submit_button("Register Target"):
            if k_name:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO targets (name, frequency) VALUES (?, ?)", (k_name, k_freq))
                conn.commit(); conn.close()
                st.rerun()

    st.subheader("Current Library")
    conn = get_db_connection()
    ledger = pd.read_sql_query("SELECT * FROM targets", conn)
    conn.close()
    for _, row in ledger.iterrows():
        lc1, lc2, lc3 = st.columns([3, 1, 0.5])
        lc1.write(f"**{row['name']}** (Last: {row['last_run']})")
        lc2.info(row['frequency'])
        if lc3.button("🗑️", key=f"rm_{row['name']}"):
            conn = get_db_connection()
            conn.execute("DELETE FROM targets WHERE name = ?", (row['name'],))
            conn.commit(); conn.close()
            st.rerun()

with t_logs:
    if st.button("Purge Logs"):
        for h in logging.root.handlers[:]: h.close(); logging.root.removeHandler(h)
        if os.path.exists(LOG_FILE): os.remove(LOG_FILE); setup_logger(); st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f: st.code("".join(f.readlines()[-50:]))
