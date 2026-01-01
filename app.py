# SCOUT TERMINAL VERSION: 3.37
# UPDATES: Fixed st.markdown HTML syntax, Absolute Modular Independence

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import logging

# --- [1. SYSTEM CORE] ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# --- [2. SIDEBAR LAYOUT] ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.37")
    
    # Custom Site Toggles
    st.subheader("📡 Deep Search Sites")
    conn = get_db()
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    for s in c_list:
        st.toggle(s, value=True, key=f"sidebar_toggle_{s}")
    
    st.divider()

    # Keyword Library
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("add_target_form", clear_on_submit=True):
            nt = st.text_input("New Target:")
            if st.form_submit_button("＋", width="stretch"):
                if nt:
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nt,))
                    conn.commit()
                    log_event("BUTTON", f"SUCCESS: Added Target '{nt}'")
                    st.rerun()
        
        t_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        for t in t_list:
            c1, c2 = st.columns([4, 1])
            c1.checkbox(t, value=True, key=f"sidebar_chk_{t}")
            if c2.button("🗑️", key=f"sidebar_del_{t}"):
                conn.execute("DELETE FROM targets WHERE name = ?", (t,))
                conn.commit()
                log_event("BUTTON", f"SUCCESS: Deleted Target '{t}'")
                st.rerun()

    # FIXED: Corrected HTML spacer syntax for Streamlit 2026
    st.markdown("<br>" * 10, unsafe_allow_html=True)
    
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        log_event("BUTTON", "SUCCESS: Manual Sweep Initiated")
        st.session_state['run_sweep'] = True
    conn.close()

# --- [3. MAIN INTERFACE] ---
t_live, t_arch, t_jobs, t_logs = st.tabs(["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"])

with t_live:
    col_main, col_status = st.columns([3, 1])
    with col_main:
        if st.session_state.get('run_sweep'):
            with st.status("Gathering Intel...") as status:
                time.sleep(1) 
                status.update(label="Sweep Complete", state="complete")
            st.session_state['run_sweep'] = False
        else:
            st.info("System Ready. Execute via Sidebar.")
    with col_status:
        st.subheader("Global Engines")
        st.toggle("eBay", value=True, key="live_ebay")
        st.toggle("Etsy", value=False, key="live_etsy")
        st.toggle("Google", value=True, key="live_google")
        st.divider()
        st.subheader("📡 Status")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                st.code(lines[-1] if lines else "Awaiting mission...")

with t_arch:
    st.subheader("📜 Historical Findings")
    conn = get_db()
    # Independent query prevents cross-tab breakage
    arch_df = pd.read_sql_query("SELECT found_date, target, source, title, price, url FROM items ORDER BY found_date DESC", conn)
    conn.close()
    if not arch_df.empty:
        st.dataframe(arch_df, width="stretch", hide_index=True)
    else:
        st.info("Archive is empty.")

with t_jobs:
    st.header("⚙️ Jobs & Config")
    # Scheduler
    st.subheader("📅 Schedule Search")
    with st.form("job_scheduler"):
        jn = st.text_input("Job Name")
        jt = st.multiselect("Keywords", t_list)
        jf = st.selectbox("Frequency", ["6 Hours", "12 Hours", "Daily"])
        if st.form_submit_button("Save Job"):
            if jn and jt:
                conn = get_db()
                conn.execute("INSERT INTO schedules (job_name, frequency, target_list) VALUES (?,?,?)", (jn, jf, ",".join(jt)))
                conn.commit(); conn.close()
                log_event("BUTTON", f"SUCCESS: Saved Job '{jn}'")
                st.rerun()

    st.divider()
    # Manage Sites (Delete logic)
    st.subheader("📡 Manage Sites")
    conn = get_db()
    sites = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
    for s in sites['domain']:
        sc1, sc2 = st.columns([5, 1])
        sc1.write(f"🌐 {s}")
        if sc2.button("🗑️", key=f"rm_site_{s}"):
            conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
            conn.commit(); conn.close()
            log_event("BUTTON", f"SUCCESS: Removed Site '{s}'")
            st.rerun()
    conn.close()

with t_logs:
    st.subheader("🛠️ System Logs")
    if st.button("🗑️ Purge Log", width="stretch"):
        open(LOG_FILE, 'w').close()
        log_event("BUTTON", "SUCCESS: Log Purged")
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-100:]))
