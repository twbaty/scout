# SCOUT TERMINAL VERSION: 3.39
# UPDATES: Deep Logic Logging, Result Hit-Count Tracking, Multi-Source Diagnostics

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import requests
import random
import logging

# --- [1. CORE SYSTEM & LOGGING] ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# --- [2. THE INTELLIGENCE ENGINE (NOW WITH TRACING)] ---
def run_scout_mission(query, engine_type, custom_domain=None):
    log_event("MISSION", f"START: Searching {engine_type if not custom_domain else custom_domain} for '{query}'")
    
    # Placeholder for SerpApi/Scraper Logic
    # In a real run, this is where the requests.get() happens
    try:
        # Simulated logic for log demonstration
        time.sleep(random.uniform(0.5, 1.5)) 
        simulated_hits = random.randint(0, 15)
        
        if simulated_hits > 0:
            log_event("DATA", f"SUCCESS: {engine_type.upper()} found {simulated_hits} items for '{query}'")
            return [{"title": f"{query} Item", "price": "$100", "url": "http://test.com"}] * simulated_hits
        else:
            log_event("DATA", f"ZERO_RESULTS: {engine_type.upper()} found nothing for '{query}'")
            return []
    except Exception as e:
        log_event("ERROR", f"FAILED: {engine_type} search for '{query}' - Reason: {str(e)}")
        return []

# --- [3. SIDEBAR LAYOUT] ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.39")
    
    # Deep Search Sites
    st.subheader("📡 Deep Search Sites")
    conn = get_db()
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    active_customs = [s for s in c_list if st.toggle(s, value=True, key=f"side_{s}")]
    
    st.divider()

    # Keyword Library
    with st.expander("🎯 Keyword Library", expanded=True):
        # (Standard Library UI remains - verified)
        t_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        selected_targets = []
        for t in t_list:
            if st.checkbox(t, value=True, key=f"chk_{t}"):
                selected_targets.append(t)

    st.markdown("<br>" * 5, unsafe_allow_html=True)
    
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state['run_sweep'] = True
    conn.close()

# --- [4. MAIN INTERFACE] ---
t_live, t_arch, t_jobs, t_logs = st.tabs(["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"])

with t_live:
    col_main, col_status = st.columns([3, 1])
    
    with col_main:
        if st.session_state.get('run_sweep'):
            all_results = []
            with st.status("📡 Sweeping Active Targets...") as status:
                for target in selected_targets:
                    # Search Custom Domains
                    for domain in active_customs:
                        res = run_scout_mission(target, "custom", custom_domain=domain)
                        all_results.extend(res)
                    
                    # Search Global Engines (If toggled)
                    if st.session_state.get('live_ebay', True):
                        res = run_scout_mission(target, "ebay")
                        all_results.extend(res)
                
                status.update(label=f"Sweep Complete: {len(all_results)} total hits.", state="complete")
            st.session_state['run_sweep'] = False
            st.dataframe(pd.DataFrame(all_results))
        else:
            st.info("System Ready.")

    with col_status:
        st.subheader("Global Engines")
        st.session_state['live_ebay'] = st.toggle("eBay", value=True)
        st.session_state['live_google'] = st.toggle("Google", value=True)
        st.divider()
        st.subheader("📡 Last Action")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                last_lines = f.readlines()[-3:] # Show last 3 lines for better context
                for line in last_lines:
                    st.caption(line.strip())

with t_logs:
    st.subheader("🛠️ Intelligence Logs")
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-100:]))
