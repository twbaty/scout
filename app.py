# SCOUT TERMINAL VERSION: 3.12
# UPDATES: Restored Config/Jobs Tab, Log Purging, Keyword Persistence

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
def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)')
    conn.execute('CREATE TABLE IF NOT EXISTS schedules (job_id INTEGER PRIMARY KEY, job_name TEXT, frequency TEXT, target_list TEXT, last_run TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS custom_sites (domain TEXT PRIMARY KEY)')
    conn.commit(); conn.close()

init_db()

# --- 3. THE ENGINE ---
def run_scout_mission(query, engine_type, custom_domain=None):
    url = "https://serpapi.com/search.json"
    q_str = str(query).strip()
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
                # Link Peeling
                direct_url = i.get("link", i.get("product_link", "#"))
                if "google.com/url" in direct_url and "url=" in direct_url:
                    direct_url = direct_url.split("url=") [-1].split("&")[0]
                p = i.get("price")
                p_val = p.get("raw", "N/A") if isinstance(p, dict) else str(p or "N/A")
                processed.append({"target": q_str, "source": label, "title": i.get("title", "No Title"), "price": p_val, "url": direct_url})
        log_system("response", f"SUCCESS: {label} found {len(processed)} items for {q_str}")
        return processed
    except Exception as e:
        log_system("error", f"FAILED: {label} -> {str(e)}")
        return []

# --- 4. SIDEBAR (PERSISTENT DATA) ---
conn = get_db_connection()
targets_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
customs_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
conn.close()

with st.sidebar:
    st.title("🛡️ SCOUT v3.12")
    
    st.subheader("🌐 Global Engines")
    g1, g2, g3 = st.columns(3)
    p_ebay = g1.toggle("Ebay", value=True)
    p_etsy = g2.toggle("Etsy", value=True)
    p_google = g3.toggle("Google", value=True)

    st.subheader("📡 Deep Search Sites")
    active_custom_sites = [s for s in customs_list if st.toggle(s, value=True, key=f"tgl_{s}")]

    st.divider()
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("lib_add_sidebar", clear_on_submit=True):
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

# --- 5. TABS (RESTORED CONFIG/JOBS) ---
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
    with st.expander("📝 Create New Schedule Job", expanded=False):
        with st.form("job_form_restored", clear_on_submit=True):
            j_name = st.text_input("Job Name:")
            j_freq = st.selectbox("Frequency:", ["Daily", "M-W-F", "Weekly", "Bi-Weekly"])
            j_targets = st.multiselect("Assign Keywords:", targets_list)
            if st.form_submit_button("Create Job"):
                if j_name and j_targets:
                    conn = get_db_connection()
                    conn.execute("INSERT INTO schedules (job_name, frequency, target_list) VALUES (?,?,?)", (j_name, j_freq, ",".join(j_targets)))
                    conn.commit(); conn.close()
                    log_system("config_change", f"Created Job: {j_name}")
                    st.rerun()

    # Display Jobs
    conn = get_db_connection(); jobs_df = pd.read_sql_query("SELECT * FROM schedules", conn); conn.close()
    for _, job in jobs_df.iterrows():
        jc1, jc2, jc3, jc4 = st.columns([2, 1, 3, 1])
        jc1.write(f"**{job['job_name']}**"); jc2.info(job['frequency']); jc3.write(f"Targets: {job['target_list']}")
        if jc4.button("🗑️", key=f"del_job_{job['job_id']}"):
            conn = get_db_connection(); conn.execute("DELETE FROM schedules WHERE job_id = ?", (job['job_id'],)); conn.commit(); conn.close()
            log_system("config_change", f"Deleted Job ID: {job['job_id']}"); st.rerun()

    st.divider()
    st.subheader("🌐 Custom Domain Registration")
    with st.form("site_reg_form", clear_on_submit=True):
        site_in = st.text_input("Domain (e.g. gumtree.com):")
        if st.form_submit_button("Register"):
            if site_in:
                conn = get_db_connection(); conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (site_in,)); conn.commit(); conn.close()
                log_system("button_click", f"Registered: {site_in}"); st.rerun()

with t_logs:
    st.subheader("🛠️ System Logs")
    if st.button("Purge Log History", type="secondary"):
        open(LOG_FILE, 'w').close()
        log_system("system", "Log history wiped.")
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-150:]))
