# SCOUT TERMINAL VERSION: 3.10
# UPDATES: Fixed NameError (Scope Fix), Decoupled Scheduling, Enhanced OS Logging

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

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)')
    conn.execute('CREATE TABLE IF NOT EXISTS schedules (job_id INTEGER PRIMARY KEY, job_name TEXT, frequency TEXT, target_list TEXT, last_run TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS custom_sites (domain TEXT PRIMARY KEY)')
    conn.commit(); conn.close()
    log_system("init", "Database verified and online.")

init_db()

# --- 3. GLOBAL DATA FETCH (Fixes NameError) ---
# We fetch this here so 'targets_list' is available to ALL tabs and the sidebar
conn = get_db_connection()
targets_df = pd.read_sql_query("SELECT name FROM targets", conn)
targets_list = targets_df['name'].tolist()
conn.close()

# --- 4. THE ENGINE ---
def run_scout_mission(query, engine_type, custom_domain=None):
    url = "https://serpapi.com/search.json"
    q = str(query).strip()
    params = {"api_key": SERP_API_KEY}
    
    if engine_type == "ebay":
        params.update({"engine": "ebay", "_nkw": q})
        res_key, label = "ebay_results", "Ebay"
    elif engine_type == "custom":
        params.update({"engine": "google", "q": f"site:{custom_domain} {q}"})
        res_key, label = "organic_results", custom_domain
    else: 
        search_q = f"site:etsy.com {q}" if engine_type == "etsy" else q
        params.update({"engine": "google_shopping", "q": search_q})
        res_key, label = "shopping_results", engine_type.title()

    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        items = data.get(res_key, [])
        processed = []
        if isinstance(items, list):
            for i in items[:15]:
                direct_url = i.get("link", i.get("product_link", "#"))
                if "google.com/url" in direct_url and "url=" in direct_url:
                    direct_url = direct_url.split("url=") [-1].split("&")[0]
                p = i.get("price")
                p_val = p.get("raw", "N/A") if isinstance(p, dict) else str(p or "N/A")
                processed.append({"target": q, "source": label, "title": i.get("title", "No Title"), "price": p_val, "url": direct_url})
        log_system("response", f"SUCCESS: {label} found {len(processed)} items.")
        return processed
    except Exception as e:
        log_system("error", f"FAILED: {label} -> {str(e)}")
        return []

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.10")
    
    st.subheader("📡 Deep Search Sites")
    conn = get_db_connection()
    customs_df = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
    conn.close()
    active_custom_sites = [s for s in customs_df['domain'] if st.toggle(s, value=True, key=f"tgl_{s}")]

    st.divider()
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("lib_form", clear_on_submit=True):
            new_t = st.text_input("New Keyword:")
            if st.form_submit_button("Add"):
                if new_t:
                    conn = get_db_connection()
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_t,))
                    conn.commit(); conn.close()
                    log_system("button_click", f"Lib Add: {new_t}")
                    st.rerun()

        selected_targets = []
        for t in targets_list: # Uses the global list
            c1, c2 = st.columns([4, 1])
            if c1.checkbox(t, value=True, key=f"sel_{t}"): selected_targets.append(t)
            if c2.button("🗑️", key=f"rm_{t}"):
                conn = get_db_connection()
                conn.execute("DELETE FROM targets WHERE name = ?", (t,))
                conn.commit(); conn.close()
                log_system("button_click", f"Lib Delete: {t}")
                st.rerun()

    st.divider()
    if st.button("🚀 EXECUTE MANUAL SWEEP", type="primary", use_container_width=True):
        st.session_state['run_sweep'] = True
        log_system("button_click", "Manual Sweep Started")

# --- 6. TABS ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs(["📡 Live Results", "📊 Dashboard", "📜 Archive", "⚙️ Config", "🛠️ Logs"])

with t_live:
    if st.session_state.get('run_sweep') and selected_targets:
        all_hits = []
        with st.status("Gathering Intel...") as status:
            for target in selected_targets:
                if st.session_state.get('p_ebay', True): all_hits.extend(run_scout_mission(target, "ebay"))
                if st.session_state.get('p_etsy', True): all_hits.extend(run_scout_mission(target, "etsy"))
                if st.session_state.get('p_google', True): all_hits.extend(run_scout_mission(target, "google"))
                for site in active_custom_sites: all_hits.extend(run_scout_mission(target, "custom", site))
            
            conn = get_db_connection()
            for h in all_hits:
                try: conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?,?,?,?,?)", (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass
            conn.commit(); conn.close()
            st.session_state['last_data'] = all_hits
            st.session_state['run_sweep'] = False
            status.update(label="Complete", state="complete")

    if 'last_data' in st.session_state:
        st.dataframe(pd.DataFrame(st.session_state['last_data']), 
                     column_config={"url": st.column_config.LinkColumn("Link", display_text="Open")},
                     use_container_width=True, hide_index=True)

with t_conf:
    st.header("⚙️ Configuration & Scheduling")
    
    st.subheader("1. Global Toggles")
    c1, c2, c3 = st.columns(3)
    c1.toggle("Ebay", value=True, key="p_ebay")
    c2.toggle("Etsy", value=True, key="p_etsy")
    c3.toggle("Google", value=True, key="p_google")
    
    st.divider()
    
    st.subheader("2. Automation Jobs")
    with st.expander("📝 Create New Schedule Job"):
        with st.form("job_form", clear_on_submit=True):
            j_name = st.text_input("Job Name:")
            j_freq = st.selectbox("Frequency:", ["Daily", "M-W-F", "Weekly", "Bi-Weekly"])
            j_targets = st.multiselect("Assign Keywords:", targets_list) # NO LONGER CRASHES
            if st.form_submit_button("Create Job"):
                if j_name and j_targets:
                    conn = get_db_connection()
                    conn.execute("INSERT INTO schedules (job_name, frequency, target_list) VALUES (?,?,?)", 
                                 (j_name, j_freq, ",".join(j_targets)))
                    conn.commit(); conn.close()
                    log_system("config_change", f"Created Job: {j_name}")
                    st.rerun()

    conn = get_db_connection()
    jobs_df = pd.read_sql_query("SELECT * FROM schedules", conn)
    conn.close()
    
    for _, job in jobs_df.iterrows():
        with st.container():
            jc1, jc2, jc3, jc4 = st.columns([2, 1, 3, 1])
            jc1.write(f"**{job['job_name']}**")
            jc2.info(job['frequency'])
            jc3.write(f"Targets: {job['target_list']}")
            if jc4.button("🗑️", key=f"del_job_{job['job_id']}"):
                conn = get_db_connection()
                conn.execute("DELETE FROM schedules WHERE job_id = ?", (job['job_id'],))
                conn.commit(); conn.close()
                log_system("config_change", f"Deleted Job ID: {job['job_id']}")
                st.rerun()

    st.divider()
    st.subheader("3. Custom Domain Management")
    with st.form("site_form", clear_on_submit=True):
        site_in = st.text_input("Domain (e.g. vintage-computer.com):")
        if st.form_submit_button("Register Site"):
            if site_in:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (site_in,))
                conn.commit(); conn.close()
                log_system("button_click", f"Registered Site: {site_in}")
                st.rerun()

with t_logs:
    st.subheader("🛠️ System Logs")
    if st.button("Purge Logs"):
        open(LOG_FILE, 'w').close()
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-150:]))
