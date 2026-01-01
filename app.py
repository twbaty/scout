# SCOUT TERMINAL VERSION: 3.31
# MODULAR LIBRARIES: Sidebar(L), Main(C), Status(R), Logs(Recovered)

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import logging

# --- 1. DATABASE & SYSTEM SETUP ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# --- 2. SIDEBAR (L) - FINALIZED LAYOUT ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.31")
    
    # Custom Sites Toggles (Stacked)
    st.subheader("📡 Deep Search Sites")
    conn = get_db()
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    # Toggles only on the Left to prevent accidental deletion
    active_customs = [s for s in c_list if st.toggle(s, value=True, key=f"side_{s}")]
    
    st.divider()

    # Keyword Library with Delete
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("lib_v31", clear_on_submit=True):
            nt = st.text_input("New Target:")
            if st.form_submit_button("＋", width="stretch"):
                if nt:
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nt,))
                    conn.commit(); st.rerun()
        
        t_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        for t in t_list:
            c_chk, c_del = st.columns([4, 1])
            c_chk.checkbox(t, value=True, key=f"c_{t}")
            if c_del.button("🗑️", key=f"d_{t}"):
                conn.execute("DELETE FROM targets WHERE name = ?", (t,))
                conn.commit(); st.rerun()

    # Dynamic spacing to keep Execute at the bottom
    st.container(height=100, border=False) 
    
    # EXECUTE SWEEP (BOTTOM LEFT)
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        # Log success of button press for troubleshooting
        log_event("BUTTON", "Execute Sweep Triggered from Sidebar")
        st.session_state['run_sweep'] = True
    conn.close()

# --- 3. MAIN INTERFACE ---
t_live, t_arch, t_jobs, t_logs = st.tabs(["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"])

with t_live:
    col_main, col_engines = st.columns([3, 1])
    
    with col_main:
        if st.session_state.get('run_sweep'):
            with st.status("Gathering Intel...") as status:
                # Mission execution would happen here
                time.sleep(1) 
                status.update(label="Sweep Complete", state="complete")
            st.session_state['run_sweep'] = False
        else:
            st.info("System Ready. Execute via Bottom-L.")

    with col_engines:
        st.subheader("Global Engines")
        st.toggle("eBay", value=True)
        st.toggle("Etsy", value=False)
        st.toggle("Google", value=True)
        
        st.divider()
        st.subheader("📡 Status")
        # Visual Status Window (Shows last log entry)
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                st.code(lines[-1] if lines else "Awaiting mission...")

with t_jobs:
    st.header("⚙️ Jobs & Config")
    
    # DELETE SITES (SAFE ZONE)
    st.subheader("📡 Manage Deep Search Sites")
    with st.expander("Edit/Delete Sites", expanded=True):
        conn = get_db()
        current_sites = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
        for s in current_sites['domain']:
            sc1, sc2 = st.columns([5, 1])
            sc1.write(f"🌐 {s}")
            if sc2.button("🗑️", key=f"rm_s_{s}"):
                conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
                conn.commit(); conn.close(); st.rerun()
        conn.close()
    
    with st.form("add_site_v31"):
        new_site = st.text_input("Add New Deep Search Domain:")
        if st.form_submit_button("Register Site"):
            if new_site:
                conn = get_db(); conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (new_site,))
                conn.commit(); conn.close(); st.rerun()

with t_logs:
    st.subheader("🛠️ System Logs")
    if st.button("🗑️ Purge Log History", width="stretch"):
        open(LOG_FILE, 'w').close()
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-100:]))
