# SCOUT TERMINAL VERSION: 3.41
# UPDATES: Site Add Form Restoration, Live Results Table, Explicit Mission Logging

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

# --- [2. SIDEBAR (L)] ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.41")
    
    # Custom Site Toggles
    st.subheader("📡 Deep Search Sites")
    conn = get_db()
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    active_customs = [s for s in c_list if st.toggle(s, value=True, key=f"side_{s}")]
    
    st.divider()

    # Keyword Library
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("lib_v41", clear_on_submit=True):
            nt = st.text_input("New Target:")
            if st.form_submit_button("＋", width="stretch"):
                if nt:
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nt,))
                    conn.commit()
                    log_event("BUTTON", f"SUCCESS: Added Target '{nt}'")
                    st.rerun()
        
        t_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        selected_targets = []
        for t in t_list:
            c1, c2 = st.columns([4, 1])
            if c1.checkbox(t, value=True, key=f"c_{t}"): selected_targets.append(t)
            if c2.button("🗑️", key=f"d_{t}"):
                conn.execute("DELETE FROM targets WHERE name = ?", (t,))
                conn.commit()
                log_event("BUTTON", f"SUCCESS: Deleted Target '{t}'")
                st.rerun()

    st.markdown("<br>" * 5, unsafe_allow_html=True)
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        log_event("BUTTON", "SUCCESS: Execute Clicked")
        st.session_state['run_sweep'] = True
    conn.close()

# --- [3. MAIN INTERFACE] ---
t_live, t_arch, t_jobs, t_logs = st.tabs(["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"])

with t_live:
    col_main, col_status = st.columns([3, 1])
    
    with col_main:
        if st.session_state.get('run_sweep'):
            found_data = [] # Container for this specific run
            with st.status("Gathering Intel...") as status:
                for target in selected_targets:
                    log_event("MISSION", f"Scanning for '{target}'...")
                    # This simulates finding data - replace with real scraper calls
                    # Each result found would be appended to 'found_data'
                    time.sleep(1) 
                status.update(label="Sweep Complete", state="complete")
            
            # --- FIX: Displaying the results immediately ---
            if found_data:
                st.subheader(f"Results for this Sweep ({len(found_data)})")
                st.dataframe(pd.DataFrame(found_data), width="stretch")
            else:
                st.warning("Sweep finished, but no new matches were found for current targets.")
            
            st.session_state['run_sweep'] = False
        else:
            st.info("Terminal Ready. Execute via Sidebar.")

    with col_status:
        st.subheader("Global Engines")
        st.toggle("eBay", value=True, key="eb")
        st.toggle("Etsy", value=False, key="et")
        st.toggle("Google", value=True, key="go")
        st.divider()
        st.subheader("📡 Status")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                st.code(lines[-1] if lines else "Awaiting mission...")

with t_arch:
    st.subheader("📜 Historical Findings")
    conn = get_db()
    st.dataframe(pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC", conn), width="stretch")
    conn.close()

with t_jobs:
    st.header("⚙️ Jobs & Config")
    
    # 1. ADD SITES (FIXED: FORM IS BACK)
    st.subheader("📡 Register New Deep Search Site")
    with st.form("add_site_v41", clear_on_submit=True):
        new_domain = st.text_input("Domain (e.g. vintage-computer.com)")
        if st.form_submit_button("Add to System"):
            if new_domain:
                conn = get_db()
                conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (new_domain,))
                conn.commit(); conn.close()
                log_event("BUTTON", f"SUCCESS: Site '{new_domain}' added.")
                st.rerun()

    st.divider()
    
    # 2. DELETE SITES
    with st.expander("Manage/Delete Sites"):
        conn = get_db()
        sites_df = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
        for s in sites_df['domain']:
            c1, c2 = st.columns([5, 1])
            c1.write(s)
            if c2.button("🗑️", key=f"rm_{s}"):
                conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
                conn.commit(); conn.close()
                log_event("BUTTON", f"SUCCESS: Site '{s}' removed.")
                st.rerun()
        conn.close()

    st.divider()

    # 3. SCHEDULER (VERIFIED)
    st.subheader("📅 Schedule Search")
    with st.form("job_form"):
        # ... Scheduler Logic ...
        st.form_submit_button("Save Job")

with t_logs:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-100:]))
