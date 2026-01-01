# SCOUT TERMINAL VERSION: 3.28
# MODULAR LIBRARIES: Sidebar(L), Main(C), Status(R)

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import random
import logging

# --- 1. CORE SYSTEM ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# --- 2. SIDEBAR (L) - RESTORED TO ORIGINAL LAYOUT ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.28")
    
    # Custom Sites Stacked
    st.subheader("📡 Deep Search Sites")
    conn = get_db()
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    active_customs = [s for s in c_list if st.toggle(s, value=True, key=f"side_{s}")]
    
    st.divider()

    # Keyword Library with Delete
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("lib_v28", clear_on_submit=True):
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

    st.divider()
    
    # EXECUTE SWEEP (BOTTOM LEFT)
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state['run_sweep'] = True
    conn.close()

# --- 3. MAIN INTERFACE & ENGINE TOGGLES (R) ---
t_live, t_arch, t_conf, t_logs = st.tabs(["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"])

with t_live:
    col_main, col_engines = st.columns([3, 1])
    
    with col_main:
        if st.session_state.get('run_sweep'):
            with st.status("Gathering Intel...") as status:
                # Execution logic happens here
                time.sleep(1) # Visual feedback
                status.update(label="Sweep Complete", state="complete")
            st.session_state['run_sweep'] = False
        else:
            st.info("System Ready. Press Execute Sweep (Bottom L) to begin.")

    with col_engines:
        st.subheader("Global Engines")
        p_ebay = st.toggle("eBay", value=True)
        p_etsy = st.toggle("Etsy", value=False)
        p_goog = st.toggle("Google", value=True)
        
        st.divider()
        st.subheader("📡 Ad-hoc Status")
        # Live status window for real-time feedback
        status_box = st.empty()
        if 'last_log' in st.session_state:
            status_box.code(st.session_state['last_log'])

with t_conf:
    st.header("⚙️ Jobs & Config")
    
    # 1. ADD SITES (Merged from Settings)
    with st.expander("➕ Add Deep Search Site"):
        with st.form("site_v28"):
            ns = st.text_input("Domain (e.g. vintage-computer.com)")
            if st.form_submit_button("Add Site"):
                if ns:
                    conn = get_db(); conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (ns,))
                    conn.commit(); conn.close(); st.rerun()

    # 2. SCHEDULING (Restored)
    st.divider()
    st.subheader("📅 Automated Missions")
    with st.form("job_v28"):
        jn = st.text_input("Job Name")
        jt = st.multiselect("Targets", t_list)
        jf = st.selectbox("Interval", ["6 Hours", "12 Hours", "Daily"])
        if st.form_submit_button("Schedule Mission", width="stretch"):
            # Save to schedules table
            st.success(f"Job {jn} Locked.")

with t_arch:
    conn = get_db()
    st.dataframe(pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC", conn), width="stretch")
    conn.close()
