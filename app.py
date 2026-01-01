# SCOUT TERMINAL VERSION: 3.7
# UPDATES: Direct URL Peeling, Button Telemetry, OS-Style Logging

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
    """Logs every button press and state change for troubleshooting."""
    msg = f"[{event_type.upper()}] {details}"
    logging.info(msg)

def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY, frequency TEXT DEFAULT "Manual", last_run TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS custom_sites (domain TEXT PRIMARY KEY)')
    conn.commit(); conn.close()
    log_system("init", "Database schema verified.")

init_db()

# --- 3. THE ENGINE (LINK PEELING ENABLED) ---
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

    log_system("request", f"Launching mission for {label} -> {q}")
    
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        items = data.get(res_key, [])
        log_system("response", f"{label} returned {len(items)} results (Status: {r.status_code})")
        
        processed = []
        if isinstance(items, list):
            for i in items[:15]:
                # LINK PEELING: Prioritize direct merchant links over Google redirects
                direct_url = i.get("link", i.get("product_link", "#"))
                if "google.com/url" in direct_url and "url=" in direct_url:
                    # Attempt to extract the actual site from the Google redirect string
                    direct_url = direct_url.split("url=")[-1].split("&")[0]
                
                p = i.get("price")
                p_val = p.get("raw", "N/A") if isinstance(p, dict) else str(p or "N/A")
                
                processed.append({
                    "target": q, "source": label, "title": i.get("title", i.get("name", "No Title")),
                    "price": p_val, "url": direct_url
                })
        return processed
    except Exception as e:
        log_system("error", f"Mission failure on {label}: {str(e)}")
        return []

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.7")
    
    # Custom Site Toggles (Requested: On/Off control for deep sites)
    st.subheader("📡 Deep Search Sites")
    conn = get_db_connection()
    customs_df = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
    conn.close()
    
    active_custom_sites = []
    for s in customs_df['domain']:
        if st.toggle(s, value=True, key=f"tgl_{s}"):
            active_custom_sites.append(s)

    st.divider()
    with st.expander("🎯 Target Library", expanded=True):
        with st.form("sidebar_target_form", clear_on_submit=True):
            new_target = st.text_input("New Keyword:")
            if st.form_submit_button("Add"):
                if new_target:
                    conn = get_db_connection()
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_target,))
                    conn.commit(); conn.close()
                    log_system("button_click", f"Added target: {new_target}")
                    st.rerun()

        conn = get_db_connection()
        t_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        conn.close()
        
        selected_targets = []
        for t in t_list:
            c1, c2 = st.columns([4, 1])
            if c1.checkbox(t, value=True, key=f"sel_{t}"): selected_targets.append(t)
            if c2.button("🗑️", key=f"rm_{t}"):
                conn = get_db_connection()
                conn.execute("DELETE FROM targets WHERE name = ?", (t,))
                conn.commit(); conn.close()
                log_system("button_click", f"Deleted target: {t}")
                st.rerun()

    st.divider()
    if st.button("🚀 EXECUTE SWEEP", type="primary", use_container_width=True):
        st.session_state['run_sweep'] = True
        log_system("button_click", "Manual Sweep Executed.")

# --- 5. TABS ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs(["📡 Live", "📊 Stats", "📜 Archive", "⚙️ Config", "🛠️ Logs"])

with t_live:
    if st.session_state.get('run_sweep') and selected_targets:
        all_hits = []
        with st.status("Executing Scans...") as status:
            for target in selected_targets:
                if st.session_state.get('p_ebay', True): all_hits.extend(run_scout_mission(target, "ebay"))
                if st.session_state.get('p_etsy', True): all_hits.extend(run_scout_mission(target, "etsy"))
                if st.session_state.get('p_google', True): all_hits.extend(run_scout_mission(target, "google"))
                for site in active_custom_sites:
                    all_hits.extend(run_scout_mission(target, "custom", site))
            
            conn = get_db_connection()
            for h in all_hits:
                try: conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?,?,?,?,?)", (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass
            conn.commit(); conn.close()
            st.session_state['last_data'] = all_hits
            st.session_state['run_sweep'] = False
            status.update(label="Scanning Complete", state="complete")

    if 'last_data' in st.session_state:
        st.dataframe(pd.DataFrame(st.session_state['last_data']), 
                     column_config={"url": st.column_config.LinkColumn("Link", display_text="Open Item")},
                     use_container_width=True, hide_index=True)

with t_conf:
    st.subheader("Global Marketplace Toggles")
    c1, c2, c3 = st.columns(3)
    c1.toggle("Ebay", value=True, key="p_ebay")
    c2.toggle("Etsy", value=True, key="p_etsy")
    c3.toggle("Google Shopping", value=True, key="p_google")
    
    st.divider()
    st.subheader("Custom Site Registration")
    with st.form("conf_site_form", clear_on_submit=True):
        site_in = st.text_input("Domain (e.g. vintage-computer.com):")
        if st.form_submit_button("Register"):
            if site_in:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (site_in,))
                conn.commit(); conn.close()
                log_system("button_click", f"Registered site: {site_in}")
                st.rerun()

with t_logs:
    st.subheader("Telemetry & System Journal")
    if st.button("Wipe Logs"):
        open(LOG_FILE, 'w').close()
        log_system("system", "Log history wiped.")
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-100:]))
