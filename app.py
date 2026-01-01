# SCOUT TERMINAL VERSION: 3.33
# UPDATES: Sidebar Execute @ Bottom, Restored Scheduler Form, Site Management in Config

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import logging

# --- 1. CORE SYSTEM ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# --- 2. SIDEBAR (L) ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.33")
    
    # Custom Sites Toggles (Stacked)
    st.subheader("📡 Deep Search Sites")
    conn = get_db()
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    active_customs = [s for s in c_list if st.toggle(s, value=True, key=f"side_{s}")]
    
    st.divider()

    # Keyword Library
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("lib_v33", clear_on_submit=True):
            nt = st.text_input("New Target:")
            if st.form_submit_button("＋", width="stretch"):
                if nt:
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nt,))
                    conn.commit(); log_event("DB", f"Button Pressed: Added {nt}"); st.rerun()
        
        t_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        for t in t_list:
            c1, c2 = st.columns([4, 1])
            c1.checkbox(t, value=True, key=f"c_{t}")
            if c2.button("🗑️", key=f"d_{t}"):
                conn.execute("DELETE FROM targets WHERE name = ?", (t,))
                conn.commit(); log_event("DB", f"Button Pressed: Deleted {t}"); st.rerun()

    # Manual Spacer to push Execute to the bottom
    st.container(height=100, border=False) 
    
    # EXECUTE SWEEP (BOTTOM LEFT)
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        log_event("BUTTON", "Manual Sweep Executed")
        st.session_state['run_sweep'] = True
    conn.close()

# --- 3. MAIN INTERFACE ---
t_live, t_arch, t_jobs, t_logs = st.tabs(["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"])

with t_jobs:
    st.header("⚙️ Jobs & Config")
    
    # SECTION 1: SCHEDULING (RESTORED)
    st.subheader("📅 Schedule Search")
    with st.form("schedule_v33", clear_on_submit=True):
        j_name = st.text_input("Job Name")
        j_targets = st.multiselect("Keywords", t_list)
        j_freq = st.selectbox("Frequency", ["6 Hours", "12 Hours", "Daily"])
        
        if st.form_submit_button("Save Job", width="stretch"):
            if j_name and j_targets:
                conn = get_db()
                conn.execute("INSERT INTO schedules (job_name, frequency, target_list) VALUES (?,?,?)", 
                             (j_name, j_freq, ",".join(j_targets)))
                conn.commit(); conn.close()
                log_event("JOB", f"Button Pressed: Saved {j_name}")
                st.rerun()

    st.divider()

    # SECTION 2: SITE MANAGEMENT (ADD/DELETE)
    st.subheader("📡 Manage Sites")
    with st.expander("Current Sites (Delete)"):
        conn = get_db()
        for s in pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain']:
            sc1, sc2 = st.columns([5, 1])
            sc1.write(s)
            if sc2.button("🗑️", key=f"rm_site_{s}"):
                conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
                conn.commit(); conn.close(); log_event("DB", f"Button Pressed: Removed Site {s}"); st.rerun()
        conn.close()
    
    with st.form("add_site_v33", clear_on_submit=True):
        ns = st.text_input("Add Domain:")
        if st.form_submit_button("Add Site"):
            if ns:
                conn = get_db(); conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (ns,))
                conn.commit(); conn.close(); log_event("DB", f"Button Pressed: Added Site {ns}"); st.rerun()

with t_logs:
    st.subheader("🛠️ System Logs")
    if st.button("🗑️ Purge Log", width="stretch"):
        open(LOG_FILE, 'w').close()
        log_event("BUTTON", "Log Purged")
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-100:]))
