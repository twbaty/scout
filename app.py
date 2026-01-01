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

st.markdown("""
    <style>
    .stAppDeployButton {display:none;}
    [data-testid="stDecoration"] {display:none;}
    div[data-testid="stTabList"] {
        position: sticky;
        top: 0;
        background-color: white;
        z-index: 999;
        padding-top: 10px;
        border-bottom: 1px solid #f0f2f6;
    }
    </style>
    """, unsafe_allow_html=True)

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
        h = logging.FileHandler(LOG_FILE)
        h.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        l.addHandler(h)
    return l

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
        logger.info(f"Sweep: {engine} | Target: {query} | Status: {response.status_code}")
        
        raw_items = []
        if engine == "ebay": raw_items = data.get("ebay_results", [])
        elif engine == "etsy": raw_items = data.get("etsy_results", [])
        elif engine == "google_shopping": raw_items = data.get("shopping_results", [])

        results = []
        # Normalizing Source Labels for Dashboard consistency
        label_map = {"ebay": "Ebay", "etsy": "Etsy", "google_shopping": "Google Shopping"}
        source_label = label_map.get(engine, engine.title())

        if isinstance(raw_items, list):
            for i in raw_items[:20]:
                p = i.get("price")
                price_str = p.get("raw", "N/A") if isinstance(p, dict) else (p if p else "N/A")
                results.append({
                    "target": query, "source": source_label, "title": i.get("title", "No Title"),
                    "price": price_str, "url": i.get("link", i.get("product_link", "#"))
                })
        return results
    except Exception as e:
        logger.error(f"Error on {engine}: {str(e)}")
        return []

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ SCOUT")
    with st.expander("➕ Quick Add Target", expanded=True):
        quick_k = st.text_input("Keyword:", key="sb_quick_k")
        if st.button("Add to List", use_container_width=True):
            if quick_k:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO targets (name, frequency) VALUES (?, 'Manual')", (quick_k,))
                conn.commit(); conn.close()
                st.rerun()
    st.divider()
    st.write("### Active Targets")
    conn = get_db_connection()
    targets_df = pd.read_sql_query("SELECT name FROM targets", conn)
    conn.close()
    
    selected_targets = []
    for t in targets_df['name']:
        c_chk, c_del = st.columns([4, 1])
        if c_chk.checkbox(t, value=True, key=f"sb_chk_{t}"):
            selected_targets.append(t)
        if c_del.button("🗑️", key=f"sb_del_{t}"):
            conn = get_db_connection()
            conn.execute("DELETE FROM targets WHERE name = ?", (t,))
            conn.commit(); conn.close()
            st.rerun()
    st.divider()
    run_mission = st.button("🚀 EXECUTE SWEEP", use_container_width=True, type="primary")

# --- 5. TABS ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs(["📡 Live", "📊 Dashboard", "📜 Archive", "⚙️ Config", "🛠️ Logs"])

with t_live:
    if run_mission and selected_targets:
        all_hits = []
        with st.status("Gathering Intel...", expanded=True) as status:
            for target in selected_targets:
                st.write(f"Scouting: **{target}**")
                if st.session_state.get('p_ebay', True): all_hits.extend(run_scout_mission(target, "ebay"))
                if st.session_state.get('p_etsy', True): all_hits.extend(run_scout_mission(target, "etsy"))
                if st.session_state.get('p_google', True): all_hits.extend(run_scout_mission(target, "google_shopping"))
                
                conn = get_db_connection()
                conn.execute("UPDATE targets SET last_run = ? WHERE name = ?", (datetime.now().strftime("%Y-%m-%d %H:%M"), target))
                conn.commit(); conn.close()
            
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
        st.info("System Ready. Add/Select keywords on the left.")

with t_dash:
    conn = get_db_connection()
    df_all = pd.read_sql_query("SELECT source, target FROM items", conn)
    conn.close()
    if not df_all.empty:
        st.subheader("🎯 Intelligence Overview")
        # Standardizing pivot to handle any weird data cases
        heatmap = df_all.groupby(['target', 'source']).size().unstack(fill_value=0)
        st.table(heatmap)

with t_arch:
    st.header("Intelligence Archive")
    conn = get_db_connection()
    arch_df = pd.read_sql_query("SELECT found_date, source, target, title, price, url FROM items ORDER BY found_date DESC LIMIT 100", conn)
    conn.close()
    st.dataframe(arch_df, column_config={"url": st.column_config.LinkColumn("Link")}, use_container_width=True, hide_index=True)

with t_conf:
    st.header("⚙️ Configuration")
    st.subheader("1. Search Engines")
    c1, c2, c3 = st.columns(3)
    c1.toggle("eBay", value=True, key="p_ebay")
    c2.toggle("Etsy", value=True, key="p_etsy")
    c3.toggle("Google Shopping", value=True, key="p_google")
    
    st.divider()
    st.subheader("2. Target Automation")
    conn = get_db_connection()
    sched_df = pd.read_sql_query("SELECT * FROM targets", conn)
    conn.close()
    
    options = ["Manual", "Daily", "Weekly"]
    for _, row in sched_df.iterrows():
        sc1, sc2, sc3 = st.columns([3, 2, 1])
        sc1.write(f"**{row['name']}**")
        
        # --- THE FIX: SAFETY CHECK FOR INDEX ---
        current_val = row['frequency'] if row['frequency'] in options else "Manual"
        idx = options.index(current_val)
        
        new_freq = sc2.selectbox("Freq:", options, index=idx, key=f"f_{row['name']}")
        if new_freq != row['frequency']:
            conn = get_db_connection()
            conn.execute("UPDATE targets SET frequency = ? WHERE name = ?", (new_freq, row['name']))
            conn.commit(); conn.close()
            st.rerun()
        sc3.write(f"Run: {row['last_run']}")

with t_logs:
    if st.button("Clear Log History"):
        open(LOG_FILE, 'w').close()
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-50:]))
