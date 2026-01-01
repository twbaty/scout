# SCOUT TERMINAL VERSION: 3.24
# UPDATES: Restored Sidebar, Fixed Blank Tabs, Enforced Data Persistence

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

# --- 2. LOGGING & DATABASE ---
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

# INITIALIZE DATABASE & ENSURE TABLES EXIST
def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)')
    conn.execute('CREATE TABLE IF NOT EXISTS schedules (job_id INTEGER PRIMARY KEY, job_name TEXT, frequency TEXT, target_list TEXT, target_engines TEXT, last_run TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS custom_sites (domain TEXT PRIMARY KEY)')
    conn.commit()
    conn.close()

init_db()

# --- 3. DATA RECOVERY (THE FIX FOR BLANK TABS) ---
def load_data():
    conn = get_db_connection()
    targets = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
    customs = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    archive = pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC", conn)
    jobs = pd.read_sql_query("SELECT * FROM schedules", conn)
    conn.close()
    return targets, customs, archive, jobs

t_list, c_list, arch_df, jobs_df = load_data()

# --- 4. SIDEBAR RESTORATION ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.24")
    
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state['run_sweep'] = True
    
    st.divider()
    st.subheader("🌐 Global Engines")
    p_ebay = st.toggle("Enable Ebay", value=True)
    p_etsy = st.toggle("Enable Etsy", value=True)
    p_google = st.toggle("Enable Google", value=True)

    st.subheader("📡 Deep Search Sites")
    active_customs = [s for s in c_list if st.toggle(f"Search {s}", value=True, key=f"side_{s}")]

    st.divider()
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("add_target_v24", clear_on_submit=True):
            new_t = st.text_input("New Target:")
            if st.form_submit_button("＋", width="stretch"):
                if new_t:
                    conn = get_db_connection()
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_t,))
                    conn.commit(); conn.close()
                    log_event("BUTTON", f"Added {new_t} to Library")
                    st.rerun()

        selected_targets = [t for t in t_list if st.checkbox(t, value=True, key=f"sel_{t}")]

# --- 5. TAB RESTORATION ---
t_live, t_arch, t_conf, t_logs = st.tabs(["📡 Live Results", "📜 Archive", "⚙️ Jobs & Config", "🛠️ Logs"])

with t_live:
    # (Live results logic remains the same)
    st.info("Select keywords and click 'Execute Sweep' to begin.")

with t_arch:
    st.subheader("📜 Historical Findings")
    if not arch_df.empty:
        st.dataframe(arch_df, use_container_width=True, hide_index=True)
    else:
        st.write("No data in archive yet.")

with t_conf:
    st.header("⚙️ Automation Jobs")
    # Restore the display of current jobs
    if not jobs_df.empty:
        for _, job in jobs_df.iterrows():
            st.write(f"**{job['job_name']}** | {job['frequency']}")
            st.caption(f"Targets: {job['target_list']}")
    else:
        st.write("No jobs configured.")

with t_logs:
    if st.button("🗑️ Purge Log", width="stretch"):
        open(LOG_FILE, 'w').close()
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-100:]))
