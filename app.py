# SCOUT TERMINAL VERSION: 3.18
# UPDATES: Restored Log Purge, Global Tab Scoping, Hardened Trace Logging

import streamlit as st
import pandas as pd
import sqlite3
import requests
import os
import time
import random
import logging

# --- 1. CORE SYSTEM SETUP ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

if "SERPAPI_KEY" in st.secrets:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
else:
    st.error("🔑 Missing SerpApi Key")
    st.stop()

# --- 2. LOGGING & DATABASE ---
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def log_system(level, msg):
    logging.info(f"[{level.upper()}] {msg}")

def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)')
    conn.execute('CREATE TABLE IF NOT EXISTS schedules (job_id INTEGER PRIMARY KEY, job_name TEXT, frequency TEXT, target_list TEXT, target_engines TEXT, last_run TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS custom_sites (domain TEXT PRIMARY KEY)')
    conn.commit(); conn.close()

init_db()

# --- 3. THE ENGINE ---
def run_scout_mission(query, engine_type, custom_domain=None):
    url = "https://serpapi.com/search.json"
    q_str = str(query).strip()
    params = {"api_key": SERP_API_KEY, "engine": engine_type, "device": "desktop", "hl": "en"}
    
    if engine_type == "ebay":
        params.update({"_nkw": q_str, "ebay_domain": "ebay.com"})
        res_key = "ebay_results"
    elif engine_type == "custom":
        params.update({"engine": "google", "q": f"site:{custom_domain} {q_str}"})
        res_key = "organic_results"
    else: 
        search_q = f"site:etsy.com {q_str}" if engine_type == "etsy" else q_str
        params.update({"engine": "google_shopping", "q": search_q})
        res_key = "shopping_results"

    try:
        time.sleep(random.uniform(1.5, 3.0)) 
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
        
        info = data.get("search_information", {})
        total = info.get("total_results", 0)
        items = data.get(res_key, [])
        
        log_system("trace", f"{engine_type.upper()} '{q_str}': Found {total} results.")
        
        processed = []
        if isinstance(items, list):
            for i in items[:15]:
                p_val = i.get("price")
                if isinstance(p_val, dict): p_val = p_val.get("raw", "N/A")
                processed.append({
                    "target": q_str, "source": engine_type if engine_type != "custom" else custom_domain, 
                    "title": i.get("title", "No Title"), "price": str(p_val), "url": i.get("link", "#")
                })
        return processed
    except Exception as e:
        log_system("error", f"Mission Failed: {str(e)}")
        return []

# --- 4. DATA RECOVERY ---
conn = get_db_connection()
targets_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
customs_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
conn.close()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.18")
    p_ebay = st.toggle("Enable Ebay", value=True)
    p_etsy = st.toggle("Enable Etsy", value=True)
    p_google = st.toggle("Enable Google", value=True)
    active_custom_sites = [s for s in customs_list if st.toggle(f"Search {s}", value=True, key=f"t_s_{s}")]

    st.divider()
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("lib_add_v18", clear_on_submit=True):
            new_t = st.text_input("New Target:")
            if st.form_submit_button("＋"):
                if new_t:
                    conn = get_db_connection(); conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_t,)); conn.commit(); conn.close()
                    st.rerun()
        selected_targets = [t for t in targets_list if st.checkbox(t, value=True, key=f"sel_{t}")]

    if st.button("🚀 EXECUTE SWEEP", type="primary", use_container_width=True):
        st.session_state['run_sweep'] = True

# --- 6. TABS & LOG PURGE ---
t_live, t_arch, t_conf, t_logs = st.tabs(["📡 Live Results", "📜 Archive", "⚙️ Jobs & Config", "🛠️ Logs"])

with t_live:
    if st.session_state.get('run_sweep') and selected_targets:
        all_hits = []
        with st.status("Gathering Intel...") as status:
            for target in selected_targets:
                if p_ebay: all_hits.extend(run_scout_mission(target, "ebay"))
                if p_etsy: all_hits.extend(run_scout_mission(target, "etsy"))
                if p_google: all_hits.extend(run_scout_mission(target, "google"))
                for site in active_custom_sites: all_hits.extend(run_scout_mission(target, "custom", site))
            
            conn = get_db_connection()
            for h in all_hits:
                try: conn.execute("INSERT OR REPLACE INTO items (target, source, title, price, url) VALUES (?,?,?,?,?)", (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass
            conn.commit(); conn.close()
            st.session_state['last_data'] = all_hits
            st.session_state['run_sweep'] = False
            status.update(label="Sweep Complete", state="complete")

    if 'last_data' in st.session_state:
        st.dataframe(pd.DataFrame(st.session_state['last_data']), use_container_width=True, hide_index=True)

with t_conf:
    st.header("⚙️ Automation Jobs")
    # Job form logic remains...

with t_logs:
    st.subheader("🛠️ System Logs")
    if st.button("🗑️ Purge Log History", type="secondary"):
        open(LOG_FILE, 'w').close()
        log_system("system", "Log history wiped by user.")
        st.rerun()
    
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-100:]))
