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

# Hide the "Deploy" button and other top-bar clutter for a cleaner look
st.markdown("""
    <style>
    .stAppDeployButton {display:none;}
    [data-testid="stDecoration"] {display:none;}
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

# --- 3. SCOUTING LOGIC ---
def run_scout_mission(query, engine):
    url = "https://serpapi.com/search.json"
    params = {"api_key": SERP_API_KEY, "engine": engine}
    if engine == "ebay": params["_nkw"] = query
    else: params["q"] = query

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        raw_items = []
        if engine == "ebay": raw_items = data.get("ebay_results", [])
        elif engine == "etsy": raw_items = data.get("etsy_results", [])
        elif engine == "google_shopping": raw_items = data.get("shopping_results", [])

        if not isinstance(raw_items, list): return []

        results = []
        for i in raw_items[:20]:
            price_val = i.get("price")
            if isinstance(price_val, dict): price_val = price_val.get("raw", "N/A")
            
            results.append({
                "target": query,
                "source": engine.replace("_", " ").capitalize(),
                "title": i.get("title", "No Title"),
                "price": price_val if price_val else "N/A",
                "url": i.get("link", i.get("product_link", "#"))
            })
        return results
    except Exception as e:
        logger.error(f"Failure on {engine}: {str(e)}")
        return []

# --- 4. SIDEBAR (Integrated Target Management) ---
with st.sidebar:
    st.title("🛡️ SCOUT")
    
    # Section: Add New
    with st.expander("➕ Register New Target", expanded=False):
        new_k = st.text_input("Keyword:", key="sb_new_k")
        if st.button("Add to Library", use_container_width=True):
            if new_k:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_k,))
                conn.commit(); conn.close()
                st.rerun()

    st.divider()
    
    # Section: Selection & Deletion
    st.write("### Mission Library")
    conn = get_db_connection()
    targets_df = pd.read_sql_query("SELECT name FROM targets", conn)
    conn.close()
    
    selected_targets = []
    for t in targets_df['name']:
        col_t, col_d = st.columns([4, 1])
        if col_t.checkbox(t, value=True, key=f"chk_{t}"):
            selected_targets.append(t)
        if col_d.button("🗑️", key=f"del_{t}"):
            conn = get_db_connection()
            conn.execute("DELETE FROM targets WHERE name = ?", (t,))
            conn.commit(); conn.close()
            st.rerun()
    
    st.divider()
    run_mission = st.button("🚀 START SWEEP", use_container_width=True, type="primary")

# --- 5. TABS ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs(["📡 Live", "📊 Dashboard", "📜 Archive", "⚙️ Config", "🛠️ Logs"])

with t_live:
    if run_mission and selected_targets:
        all_hits = []
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for target in selected_targets:
                st.write(f"Scouting: **{target}**")
                if st.session_state.get('p_ebay', True): all_hits.extend(run_scout_mission(target, "ebay"))
                if st.session_state.get('p_etsy', True): all_hits.extend(run_scout_mission(target, "etsy"))
                if st.session_state.get('p_google', True): all_hits.extend(run_scout_mission(target, "google_shopping"))
                
                conn = get_db_connection()
                conn.execute("UPDATE targets SET last_run = ? WHERE name = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), target))
                conn.commit(); conn.close()
                time.sleep(0.5)
            
            conn = get_db_connection()
            for h in all_hits:
                try: conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?, ?, ?, ?, ?)", (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass 
            conn.commit(); conn.close()
            st.session_state['last_results'] = all_hits
            status.update(label="✅ Sweep Complete!", state="complete")

    if st.session_state.get('last_results'):
        st.dataframe(pd.DataFrame(st.session_state['last_results']), use_container_width=True, hide_index=True)
    else:
        st.info("System Ready. Select targets in the sidebar and press Start Sweep.")

with t_dash:
    conn = get_db_connection()
    df_all = pd.read_sql_query("SELECT source, target FROM items", conn)
    conn.close()
    if not df_all.empty:
        heatmap = df_all.groupby(['target', 'source']).size().unstack(fill_value=0)
        st.subheader("🎯 Marketplace Distribution")
        st.table(heatmap)

with t_arch:
    st.header("Intelligence Archive")
    arch_space, arch_ctrl = st.columns([4, 1])
    with arch_ctrl:
        depth = st.selectbox("View Depth:", [50, 100, 500, "All"], index=0)
    
    limit = "" if depth == "All" else f"LIMIT {depth}"
    conn = get_db_connection()
    arch_df = pd.read_sql_query(f"SELECT found_date, source, target, title, price, url FROM items ORDER BY found_date DESC {limit}", conn)
    conn.close()
    st.dataframe(arch_df, column_config={"url": st.column_config.LinkColumn("Link")}, use_container_width=True, hide_index=True, height=600)

with t_conf:
    st.header("Engine Configuration")
    st.subheader("Marketplace Access")
    c1, c2, c3 = st.columns(3)
    c1.toggle("eBay", value=True, key="p_ebay")
    c2.toggle("Etsy", value=True, key="p_etsy")
    c3.toggle("Google Shopping", value=True, key="p_google")

with t_logs:
    if st.button("Purge Logs"):
        for h in logging.root.handlers[:]: h.close(); logging.root.removeHandler(h)
        if os.path.exists(LOG_FILE): os.remove(LOG_FILE); setup_logger(); st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f: st.code("".join(f.readlines()[-50:]))
