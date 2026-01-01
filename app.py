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

# API Setup
try:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
except:
    st.error("Missing API Key in .streamlit/secrets.toml")
    st.stop()

# --- LOGGING SETUP ---
LOG_FILE = 'scout.log'
def setup_logger():
    l = logging.getLogger("SCOUT")
    l.setLevel(logging.INFO)
    if not l.handlers:
        h = logging.FileHandler(LOG_FILE, encoding='utf-8')
        h.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        l.addHandler(h)
    return l

logger = setup_logger()

# --- 2. DATABASE & NORMALIZATION ---
def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY, frequency TEXT DEFAULT "Manual", last_run TIMESTAMP)')
    
    # Clean up any casing issues in existing data
    conn.execute("UPDATE items SET source = 'Ebay' WHERE LOWER(source) = 'ebay'")
    conn.execute("UPDATE items SET source = 'Etsy' WHERE LOWER(source) = 'etsy'")
    conn.execute("UPDATE items SET source = 'Google Shopping' WHERE LOWER(source) LIKE 'google%'")
    conn.commit(); conn.close()

init_db()

# --- 3. THE REFINED SCOUT LOGIC ---
def run_scout_mission(query, engine_key):
    url = "https://serpapi.com/search.json"
    clean_query = str(query).strip()
    
    # ROUTING LOGIC: Handle the fact that SerpApi has no "etsy" engine
    if engine_key == "etsy":
        # We use Google Shopping but force it to look ONLY at Etsy
        actual_engine = "google_shopping"
        actual_query = f"site:etsy.com {clean_query}"
        source_label = "Etsy"
    elif engine_key == "ebay":
        actual_engine = "ebay"
        actual_query = clean_query
        source_label = "Ebay"
    else:
        actual_engine = "google_shopping"
        actual_query = clean_query
        source_label = "Google Shopping"

    params = {
        "api_key": SERP_API_KEY,
        "engine": actual_engine,
        "q": actual_query
    }
    
    # eBay uses _nkw instead of q
    if actual_engine == "ebay":
        params.pop("q")
        params["_nkw"] = actual_query

    try:
        response = requests.get(url, params=params, timeout=15)
        logger.info(f"Sweep: {source_label} | Query: {clean_query} | Status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"SerpApi Error: {response.text}")
            return []

        data = response.json()
        
        # Extract based on engine type
        if actual_engine == "ebay":
            raw_items = data.get("ebay_results", [])
        else:
            raw_items = data.get("shopping_results", [])

        results = []
        if isinstance(raw_items, list):
            for i in raw_items[:15]:
                p = i.get("price")
                price_str = p.get("raw", "N/A") if isinstance(p, dict) else (str(p) if p else "N/A")
                results.append({
                    "target": clean_query,
                    "source": source_label,
                    "title": i.get("title", "No Title"),
                    "price": price_str,
                    "url": i.get("link", i.get("product_link", "#"))
                })
        return results
    except Exception as e:
        logger.error(f"Mission Failed: {str(e)}")
        return []

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ SCOUT")
    with st.expander("➕ Quick Add Target", expanded=True):
        new_k = st.text_input("Keyword:", key="sb_k")
        if st.button("Add to Library", use_container_width=True):
            if new_k:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO targets (name, frequency) VALUES (?, 'Manual')", (new_k,))
                conn.commit(); conn.close()
                st.rerun()

    st.divider()
    st.write("### Active Library")
    conn = get_db_connection()
    targets_df = pd.read_sql_query("SELECT name FROM targets", conn)
    conn.close()
    
    selected_targets = []
    for t in targets_df['name']:
        c1, c2 = st.columns([4, 1])
        if c1.checkbox(t, value=True, key=f"cb_{t}"):
            selected_targets.append(t)
        if c2.button("🗑️", key=f"del_{t}"):
            conn = get_db_connection()
            conn.execute("DELETE FROM targets WHERE name = ?", (t,))
            conn.commit(); conn.close()
            st.rerun()
    
    st.divider()
    execute = st.button("🚀 EXECUTE SWEEP", use_container_width=True, type="primary")

# --- 5. INTERFACE ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs(["📡 Live", "📊 Dashboard", "📜 Archive", "⚙️ Config", "🛠️ Logs"])

with t_live:
    if execute and selected_targets:
        all_hits = []
        with st.status("Scouting Marketplaces...", expanded=True) as status:
            for target in selected_targets:
                st.write(f"Searching: **{target}**")
                if st.session_state.get('p_ebay', True): all_hits.extend(run_scout_mission(target, "ebay"))
                if st.session_state.get('p_etsy', True): all_hits.extend(run_scout_mission(target, "etsy"))
                if st.session_state.get('p_google', True): all_hits.extend(run_scout_mission(target, "google_shopping"))
            
            conn = get_db_connection()
            for h in all_hits:
                try: conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?, ?, ?, ?, ?)", (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass # Skip duplicates automatically
            conn.commit(); conn.close()
            st.session_state['last_run'] = all_hits
            status.update(label="Sweep Complete", state="complete")

    if st.session_state.get('last_run'):
        st.dataframe(pd.DataFrame(st.session_state['last_run']), use_container_width=True, hide_index=True)
    else:
        st.info("Select targets on the left to begin.")

with t_dash:
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT source, target FROM items", conn)
    conn.close()
    if not df.empty:
        df['source'] = df['source'].str.title()
        chart_data = df.groupby(['target', 'source']).size().unstack(fill_value=0)
        st.table(chart_data)

with t_arch:
    conn = get_db_connection()
    df_arch = pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC LIMIT 100", conn)
    conn.close()
    st.dataframe(df_arch, use_container_width=True, hide_index=True)

with t_conf:
    st.header("⚙️ Configuration")
    c1, c2, c3 = st.columns(3)
    c1.toggle("eBay", value=True, key="p_ebay")
    c2.toggle("Etsy", value=True, key="p_etsy")
    c3.toggle("Google Shopping", value=True, key="p_google")
    
    st.divider()
    st.subheader("Automation & Frequency")
    conn = get_db_connection()
    sched = pd.read_sql_query("SELECT * FROM targets", conn)
    conn.close()
    
    for _, row in sched.iterrows():
        r1, r2, r3 = st.columns([3, 2, 1])
        r1.write(row['name'])
        opts = ["Manual", "Daily", "Weekly"]
        cur = row['frequency'] if row['frequency'] in opts else "Manual"
        new_f = r2.selectbox("Freq", opts, index=opts.index(cur), key=f"f_{row['name']}")
        if new_f != row['frequency']:
            conn = get_db_connection()
            conn.execute("UPDATE targets SET frequency = ? WHERE name = ?", (new_f, row['name']))
            conn.commit(); conn.close()
            st.rerun()
        r3.write(row['last_run'])

with t_logs:
    if st.button("Clear Logs"):
        open(LOG_FILE, 'w').close()
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-50:]))
