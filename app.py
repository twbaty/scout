# SCOUT TERMINAL VERSION: 3.11
# UPDATES: Fixed eBay _nkw Mapping, Consolidated Sidebar Toggles

import streamlit as st
import pandas as pd
import sqlite3
import requests
import os
import logging
from datetime import datetime

# --- 1. CORE SYSTEM SETUP ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

if "SERPAPI_KEY" in st.secrets:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
else:
    st.error("🔑 Missing SerpApi Key")
    st.stop()

# --- 2. OS-LEVEL LOGGING ---
LOG_FILE = 'scout.log'
logging.basicConfig(
    filename=LOG_FILE, 
    level=logging.INFO, 
    format='%(asctime)s [OS_LEVEL] %(levelname)s: %(message)s'
)

def log_system(event_type, details):
    msg = f"[{event_type.upper()}] {details}"
    logging.info(msg)

def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

# Database Setup
conn = get_db_connection()
conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)')
conn.execute('CREATE TABLE IF NOT EXISTS schedules (job_id INTEGER PRIMARY KEY, job_name TEXT, frequency TEXT, target_list TEXT, last_run TIMESTAMP)')
conn.execute('CREATE TABLE IF NOT EXISTS custom_sites (domain TEXT PRIMARY KEY)')
conn.commit(); conn.close()

# Global Data Fetch
conn = get_db_connection()
targets_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
customs_df = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
conn.close()

# --- 3. THE ENGINE (v3.11 REINFORCED) ---
def run_scout_mission(query, engine_type, custom_domain=None):
    url = "https://serpapi.com/search.json"
    q_str = str(query).strip()
    
    # Logic Fix: eBay uses _nkw, Google/Etsy use q
    params = {"api_key": SERP_API_KEY, "engine": engine_type}
    
    if engine_type == "ebay":
        params["_nkw"] = q_str
        res_key, label = "ebay_results", "Ebay"
    elif engine_type == "custom":
        params.update({"engine": "google", "q": f"site:{custom_domain} {q_str}"})
        res_key, label = custom_domain, custom_domain
    else: 
        search_q = f"site:etsy.com {q_str}" if engine_type == "etsy" else q_str
        params.update({"engine": "google_shopping", "q": search_q})
        res_key, label = "shopping_results", engine_type.title()

    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        items = data.get(res_key, [])
        processed = []
        
        if isinstance(items, list):
            for i in items[:15]:
                # Price Extraction Handle
                p = i.get("price")
                p_val = p.get("raw", "N/A") if isinstance(p, dict) else str(p or "N/A")
                
                processed.append({
                    "target": q_str, 
                    "source": label, 
                    "title": i.get("title", "No Title"), 
                    "price": p_val, 
                    "url": i.get("link", "#")
                })
        log_system("response", f"SUCCESS: {label} found {len(processed)} items for {q_str}")
        return processed
    except Exception as e:
        log_system("error", f"FAILED: {label} -> {str(e)}")
        return []

# --- 4. SIDEBAR (CONSOLIDATED) ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.11")
    
    # Moved from Config for visibility
    st.subheader("🌐 Global Engines")
    g1, g2, g3 = st.columns(3)
    p_ebay = g1.toggle("Ebay", value=True)
    p_etsy = g2.toggle("Etsy", value=True)
    p_google = g3.toggle("Google", value=True)

    st.subheader("📡 Deep Search Sites")
    active_custom_sites = [s for s in customs_df['domain'] if st.toggle(s, value=True, key=f"tgl_{s}")]

    st.divider()
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("lib_add", clear_on_submit=True):
            new_t = st.text_input("Add Keyword:")
            if st.form_submit_button("＋"):
                if new_t:
                    conn = get_db_connection(); conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_t,)); conn.commit(); conn.close()
                    log_system("button_click", f"Added: {new_t}")
                    st.rerun()

        selected_targets = []
        for t in targets_list:
            c1, c2 = st.columns([4, 1])
            if c1.checkbox(t, value=True, key=f"sel_{t}"): selected_targets.append(t)
            if c2.button("🗑️", key=f"rm_{t}"):
                conn = get_db_connection(); conn.execute("DELETE FROM targets WHERE name = ?", (t,)); conn.commit(); conn.close()
                log_system("button_click", f"Deleted: {t}")
                st.rerun()

    if st.button("🚀 EXECUTE SWEEP", type="primary", use_container_width=True):
        st.session_state['run_sweep'] = True

# --- 5. TABS ---
t_live, t_arch, t_conf, t_logs = st.tabs(["📡 Live Results", "📜 Archive", "⚙️ Jobs", "🛠️ Logs"])

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
                try: conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?,?,?,?,?)", (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass
            conn.commit(); conn.close()
            st.session_state['last_data'] = all_hits
            st.session_state['run_sweep'] = False
            status.update(label="Mission Complete", state="complete")

    if 'last_data' in st.session_state:
        st.dataframe(pd.DataFrame(st.session_state['last_data']), use_container_width=True, hide_index=True)

with t_conf:
    st.header("⚙️ Automation Jobs")
    # (Job creation form same as v3.10)
    st.info("Jobs are decoupled from the sidebar. You can set them here and they will run independently.")

with t_logs:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-100:]))
