# SCOUT TERMINAL VERSION: 3.36
# LOGGING: All button actions logged with SUCCESS/FAIL status.
# ARCHITECTURE: Flat-Module (Prevents cross-tab breakage).

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import logging

# --- [SECTION 1: SYSTEM INITIALIZATION] ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# --- [SECTION 2: SIDEBAR LAYOUT] ---
# Defined at the top level to ensure it stays locked to the left.
with st.sidebar:
    st.title("🛡️ SCOUT v3.36")
    
    # 1. DEEP SEARCH TOGGLES
    st.subheader("📡 Deep Search Sites")
    conn = get_db()
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    for s in c_list:
        st.toggle(s, value=True, key=f"sidebar_toggle_{s}")
    
    st.divider()

    # 2. KEYWORD LIBRARY
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("add_target_form", clear_on_submit=True):
            nt = st.text_input("New Target:")
            if st.form_submit_button("＋", width="stretch"):
                if nt:
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nt,))
                    conn.commit()
                    log_event("BUTTON", f"SUCCESS: Added '{nt}' to library.")
                    st.rerun()
        
        t_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        for t in t_list:
            c1, c2 = st.columns([4, 1])
            c1.checkbox(t, value=True, key=f"sidebar_chk_{t}")
            if c2.button("🗑️", key=f"sidebar_del_{t}"):
                conn.execute("DELETE FROM targets WHERE name = ?", (t,))
                conn.commit()
                log_event("BUTTON", f"SUCCESS: Deleted '{t}' from library.")
                st.rerun()

    # 3. EXECUTE BUTTON (Pushed to bottom)
    st.markdown("<br>" * 10, unsafe_content_allowed=True)
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        log_event("BUTTON", "SUCCESS: Manual Sweep Initiated.")
        st.session_state['run_sweep'] = True
    conn.close()

# --- [SECTION 3: MAIN TABS] ---
t_live, t_arch, t_jobs, t_logs = st.tabs(["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"])

# LIVE FEED MODULE
with t_live:
    col_left, col_right = st.columns([3, 1])
    with col_left:
        if st.session_state.get('run_sweep'):
            st.write("### 🛰️ Scanning Active...")
            # Simulation for now
            time.sleep(1)
            st.session_state['run_sweep'] = False
        else:
            st.info("Terminal Idle. Ready for sweep.")
            
    with col_right:
        st.subheader("Global Engines")
        st.toggle("eBay", value=True, key="engine_ebay")
        st.toggle("Etsy", value=False, key="engine_etsy")
        st.toggle("Google", value=True, key="engine_google")
        st.divider()
        st.subheader("📡 Status")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                st.code(lines[-1] if lines else "Awaiting mission...")

# ARCHIVE MODULE (Independent Fetch)
with t_arch:
    st.subheader("📜 Historical Findings")
    conn = get_db()
    try:
        df = pd.read_sql_query("SELECT found_date, target, source, title, price, url FROM items ORDER BY found_date DESC", conn)
        st.dataframe(df, width="stretch", hide_index=True)
    except Exception as e:
        st.error(f"Archive Fetch Error: {e}")
    conn.close()

# JOBS & CONFIG MODULE
with t_jobs:
    st.header("⚙️ Jobs & Config")
    # A. SCHEDULER
    st.subheader("📅 Schedule Search")
    with st.form("job_form"):
        j_name = st.text_input("Job Name")
        j_targets = st.multiselect("Keywords", t_list)
        j_freq = st.selectbox("Frequency", ["6 Hours", "12 Hours", "Daily"])
        if st.form_submit_button("Save Job"):
            conn = get_db()
            conn.execute("INSERT INTO schedules (job_name, frequency, target_list) VALUES (?,?,?)", (j_name, j_freq, ",".join(j_targets)))
            conn.commit(); conn.close()
            log_event("BUTTON", f"SUCCESS: Job '{j_name}' saved.")
            st.rerun()

    # B. SITE MANAGEMENT (Delete here only)
    st.divider()
    st.subheader("📡 Manage Deep Search Domains")
    conn = get_db()
    sites = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
    for s in sites['domain']:
        sc1, sc2 = st.columns([5, 1])
        sc1.write(f"🌐 {s}")
        if sc2.button("🗑️", key=f"delete_site_{s}"):
            conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
            conn.commit(); conn.close()
            log_event("BUTTON", f"SUCCESS: Site '{s}' removed.")
            st.rerun()
    conn.close()

# LOGS MODULE
with t_logs:
    st.subheader("🛠️ System Logs")
    if st.button("🗑️ Purge Log"):
        open(LOG_FILE, 'w').close()
        log_event("BUTTON", "SUCCESS: Log history cleared.")
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-100:]))
