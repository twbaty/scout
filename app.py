# SCOUT TERMINAL VERSION: 3.14
# UPDATES: Per-Job Engine Toggles, Delay Logic, Forced Cache Reset

import streamlit as st
import pandas as pd
import sqlite3
import requests
import os
import time
import logging

# --- 1. CORE SYSTEM SETUP ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

if "SERPAPI_KEY" in st.secrets:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
else:
    st.error("🔑 Missing SerpApi Key")
    st.stop()

# --- 2. OS-LEVEL LOGGING ---
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s [OS_LEVEL] %(levelname)s: %(message)s')

def log_system(event_type, details):
    logging.info(f"[{event_type.upper()}] {details}")

def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)')
    # UPDATED SCHEMA: target_engines stores which sites this job uses
    conn.execute('CREATE TABLE IF NOT EXISTS schedules (job_id INTEGER PRIMARY KEY, job_name TEXT, frequency TEXT, target_list TEXT, target_engines TEXT, last_run TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS custom_sites (domain TEXT PRIMARY KEY)')
    conn.commit(); conn.close()

init_db()

# --- 3. REINFORCED ENGINE ---
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
        # Prevent API throttling with a tiny sleep
        time.sleep(0.5)
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        items = data.get(res_key, [])
        processed = []
        if isinstance(items, list):
            for i in items[:15]:
                # Peeling
                link = i.get("link", i.get("product_link", "#"))
                if "google.com/url" in link: link = link.split("url=")[-1].split("&")[0]
                
                p_val = i.get("price")
                if isinstance(p_val, dict): p_val = p_val.get("raw", "N/A")
                
                processed.append({"target": q_str, "source": label, "title": i.get("title", "No Title"), "price": str(p_val), "url": link})
        
        log_system("response", f"SUCCESS: {label} found {len(processed)} items for {q_str}")
        return processed
    except Exception as e:
        log_system("error", f"FAILED: {label} -> {str(e)}")
        return []

# --- 4. DATA FETCH ---
conn = get_db_connection()
targets_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
customs_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
conn.close()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.14")
    
    st.subheader("🌐 Global Engines")
    p_ebay = st.toggle("Enable Ebay Search", value=True)
    p_etsy = st.toggle("Enable Etsy Search", value=True)
    p_google = st.toggle("Enable Google Search", value=True)

    st.subheader("📡 Deep Search Sites")
    active_custom_sites = [s for s in customs_list if st.toggle(f"Search {s}", value=True, key=f"tgl_{s}")]

    st.divider()
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("lib_add_v14", clear_on_submit=True):
            new_t = st.text_input("Add Keyword:")
            if st.form_submit_button("＋"):
                if new_t:
                    conn = get_db_connection(); conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_t,)); conn.commit(); conn.close()
                    st.rerun()

        selected_targets = []
        for t in targets_list:
            c1, c2 = st.columns([4, 1])
            if c1.checkbox(t, value=True, key=f"sel_{t}"): selected_targets.append(t)
            if c2.button("🗑️", key=f"rm_{t}"):
                conn = get_db_connection(); conn.execute("DELETE FROM targets WHERE name = ?", (t,)); conn.commit(); conn.close()
                st.rerun()

    if st.button("🚀 EXECUTE SWEEP", type="primary", use_container_width=True):
        st.session_state['run_sweep'] = True

# --- 6. TABS ---
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
            status.update(label="Complete", state="complete")

    if 'last_data' in st.session_state:
        st.dataframe(pd.DataFrame(st.session_state['last_data']), use_container_width=True, hide_index=True)

with t_conf:
    st.header("⚙️ Automation Jobs")
    with st.expander("📝 Create New Narrow Search Job"):
        with st.form("job_v14"):
            j_name = st.text_input("Job Name:")
            j_freq = st.selectbox("Frequency:", ["Daily", "M-W-F", "Weekly"])
            j_targets = st.multiselect("Keywords:", targets_list)
            
            st.write("**Engines to Include:**")
            e_ebay = st.checkbox("Ebay", value=True)
            e_etsy = st.checkbox("Etsy", value=False)
            e_google = st.checkbox("Google", value=True)
            e_customs = st.multiselect("Deep Search Sites:", customs_list)
            
            if st.form_submit_button("Save Job"):
                engines = []
                if e_ebay: engines.append("ebay")
                if e_etsy: engines.append("etsy")
                if e_google: engines.append("google")
                engines.extend(e_customs)
                
                conn = get_db_connection()
                conn.execute("INSERT INTO schedules (job_name, frequency, target_list, target_engines) VALUES (?,?,?,?)", 
                             (j_name, j_freq, ",".join(j_targets), ",".join(engines)))
                conn.commit(); conn.close()
                st.rerun()

    # Display Jobs
    conn = get_db_connection(); j_df = pd.read_sql_query("SELECT * FROM schedules", conn); conn.close()
    for _, job in j_df.iterrows():
        st.write(f"**{job['job_name']}** ({job['frequency']})")
        st.caption(f"Targets: {job['target_list']} | Engines: {job['target_engines']}")
        if st.button("🗑️", key=f"dj_{job['job_id']}"):
            conn = get_db_connection(); conn.execute("DELETE FROM schedules WHERE job_id = ?", (job['job_id'],)); conn.commit(); conn.close()
            st.rerun()

with t_logs:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-150:]))
