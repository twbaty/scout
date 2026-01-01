# SCOUT TERMINAL VERSION: 3.27
# MODULAR LIBRARIES: Sidebar(L), Engine(C), Settings(R)

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import random
import logging

# --- [LIBRARY 1: CORE SYSTEM & 2026 COMPLIANCE] ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# --- [LIBRARY 2: SIDEBAR ARCHITECTURE (RESTORED)] ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.27")
    
    # 1. EXECUTE SWEEP (TOP)
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state['run_sweep'] = True
    
    st.divider()
    
    # 2. DEEP SEARCH SITES (STACKED)
    st.subheader("📡 Deep Search Sites")
    conn = get_db()
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    active_customs = [s for s in c_list if st.toggle(s, value=True, key=f"side_{s}")]
    
    st.divider()

    # 3. KEYWORD LIBRARY (WITH DELETE)
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("lib_v27", clear_on_submit=True):
            nt = st.text_input("New Target:")
            if st.form_submit_button("＋", width="stretch"):
                if nt:
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nt,))
                    conn.commit(); st.rerun()
        
        t_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        selected_targets = []
        for t in t_list:
            c_chk, c_del = st.columns([4, 1])
            if c_chk.checkbox(t, value=True, key=f"c_{t}"): selected_targets.append(t)
            if c_del.button("🗑️", key=f"d_{t}"):
                conn.execute("DELETE FROM targets WHERE name = ?", (t,))
                conn.commit(); st.rerun()
    conn.close()

# --- [LIBRARY 3: TAB NAVIGATION & SETTINGS RECOVERY] ---
# Tabs are defined here so they are globally accessible
t_live, t_arch, t_jobs, t_set, t_logs = st.tabs(["📡 Live", "📜 Archive", "⚙️ Jobs", "🛠️ Settings", "📝 Logs"])

with t_live:
    # Manual Overrides for current session
    col1, col2, col3 = st.columns(3)
    p_ebay = col1.toggle("eBay", value=True)
    p_etsy = col2.toggle("Etsy", value=False)
    p_goog = col3.toggle("Google", value=True)
    
    if st.session_state.get('run_sweep'):
        # Mission Logic runs here...
        st.session_state['run_sweep'] = False

with t_arch:
    st.subheader("📜 Historical Findings")
    conn = get_db()
    arch_df = pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC", conn)
    conn.close()
    if not arch_df.empty:
        st.dataframe(arch_df, width="stretch", hide_index=True)
    else:
        st.info("Archive is empty. Run a sweep to collect data.")

with t_jobs:
    st.subheader("⚙️ Automated Missions")
    conn = get_db()
    jobs_df = pd.read_sql_query("SELECT * FROM schedules", conn)
    conn.close()
    if not jobs_df.empty:
        st.dataframe(jobs_df, width="stretch", hide_index=True)
    else:
        st.caption("No jobs scheduled yet.")

with t_set:
    st.header("🛠️ System Settings")
    st.subheader("📡 Deep Search Management")
    with st.form("add_site_v27"):
        ns = st.text_input("Add Custom Site (e.g. vintage-computer.com):")
        if st.form_submit_button("Add Site", width="stretch"):
            if ns:
                conn = get_db(); conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (ns,))
                conn.commit(); conn.close(); st.rerun()

with t_logs:
    if st.button("🗑️ Purge Log History", width="stretch"):
        open(LOG_FILE, 'w').close()
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-100:]))
