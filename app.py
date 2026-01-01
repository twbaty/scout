# SCOUT TERMINAL VERSION: 3.46
# UPDATES: Final code consolidation. No structural changes. Verified all forms.

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import logging

# --- [1. CORE SYSTEM] ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# --- [2. SIDEBAR (L)] ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.46")
    
    conn = get_db()
    
    # SITE TOGGLES
    st.subheader("📡 Deep Search Sites")
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    active_customs = [s for s in c_list if st.toggle(s, value=True, key=f"side_{s}")]
    
    st.divider()

    # KEYWORD LIBRARY
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("add_keyword_v46", clear_on_submit=True):
            nk = st.text_input("New Target:")
            if st.form_submit_button("＋", width="stretch"):
                if nk:
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nk,))
                    conn.commit()
                    log_event("BUTTON", f"SUCCESS: Added Keyword '{nk}'")
                    st.rerun()
        
        t_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        selected_targets = []
        for t in t_list:
            c1, c2 = st.columns([4, 1])
            if c1.checkbox(t, value=True, key=f"sel_{t}"): selected_targets.append(t)
            if c2.button("🗑️", key=f"del_{t}"):
                conn.execute("DELETE FROM targets WHERE name = ?", (t,))
                conn.commit()
                log_event("BUTTON", f"SUCCESS: Deleted Keyword '{t}'")
                st.rerun()

    st.markdown("<br>" * 5, unsafe_allow_html=True)
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        log_event("BUTTON", "SUCCESS: Manual Sweep Initiated")
        st.session_state['run_sweep'] = True
    conn.close()

# --- [3. MAIN INTERFACE] ---
t_live, t_arch, t_jobs, t_logs = st.tabs(["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"])

# TAB: LIVE FEED
with t_live:
    c_main, c_stat = st.columns([3, 1])
    with c_main:
        if st.session_state.get('run_sweep'):
            with st.status("📡 Sweeping Engines...") as status:
                conn = get_db()
                if selected_targets:
                    placeholders = ','.join(['?'] * len(selected_targets))
                    query = f"SELECT found_date, target, source, title, price, url FROM items WHERE target IN ({placeholders}) ORDER BY found_date DESC"
                    results = pd.read_sql_query(query, conn, params=selected_targets)
                else:
                    results = pd.DataFrame()
                time.sleep(0.5)
                conn.close()
                status.update(label=f"Sweep Complete: {len(results)} items identified.", state="complete")
            
            if not results.empty:
                st.subheader(f"Results for Keywords: {', '.join(selected_targets)}")
                st.dataframe(results, use_container_width=True, hide_index=True)
            else:
                st.warning("No matches found in database for selected keywords.")
            st.session_state['run_sweep'] = False
        else:
            st.info("Terminal Ready. Select keywords and execute.")

    with c_stat:
        st.subheader("Global Engines")
        st.toggle("eBay", value=True, key="eb_v46")
        st.toggle("Etsy", value=True, key="et_v46")
        st.toggle("Google", value=True, key="go_v46")
        st.divider()
        st.subheader("📡 Status")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                st.code(lines[-1] if lines else "Ready.")

# TAB: ARCHIVE
with t_arch:
    st.subheader("📜 Historical Findings")
    conn = get_db()
    all_items = pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC", conn)
    conn.close()
    st.dataframe(all_items, use_container_width=True, hide_index=True)

# TAB: JOBS & CONFIG
with t_jobs:
    st.header("⚙️ Jobs & Config")
    
    # 1. ADD SITES
    st.subheader("📡 Register New Deep Search Site")
    with st.form("add_site_v46", clear_on_submit=True):
        ns = st.text_input("Domain (e.g. newegg.com)")
        if st.form_submit_button("Add Site"):
            if ns:
                conn = get_db()
                conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (ns,))
                conn.commit(); conn.close()
                log_event("BUTTON", f"SUCCESS: Added Site '{ns}'")
                st.rerun()

    st.divider()
    
    # 2. DELETE SITES
    with st.expander("Manage Registered Sites"):
        conn = get_db()
        sites = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
        for s in sites['domain']:
            c1, c2 = st.columns([5, 1])
            c1.write(f"🌐 {s}")
            if c2.button("🗑️", key=f"rm_site_{s}"):
                conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
                conn.commit(); conn.close()
                log_event("BUTTON", f"SUCCESS: Removed Site '{s}'")
                st.rerun()
        conn.close()

    st.divider()

    # 3. SCHEDULER
    st.subheader("📅 Schedule Search")
    with st.form("job_form_v46"):
        jn = st.text_input("Job Name")
        jt = st.multiselect("Keywords", t_list)
        jf = st.selectbox("Frequency", ["6 Hours", "12 Hours", "Daily"])
        if st.form_submit_button("Save Job"):
            if jn and jt:
                conn = get_db()
                conn.execute("INSERT INTO schedules (job_name, frequency
