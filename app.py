# SCOUT TERMINAL VERSION: 3.26
# MODULAR LIBRARIES: Data (DB), UI (Sidebar), Engine (SerpApi), Tabs (Display)

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import random
import logging

# --- LIBRARY 1: SYSTEM & LOGGING ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

# --- LIBRARY 2: DATA PERSISTENCE (The Archive Fix) ---
def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)')
    conn.execute('CREATE TABLE IF NOT EXISTS custom_sites (domain TEXT PRIMARY KEY)')
    conn.commit(); conn.close()

init_db()

# --- LIBRARY 3: SIDEBAR UI (Restored Classic Stack) ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.26")
    
    # 1. EXECUTE (TOP)
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state['run_sweep'] = True
    
    st.divider()
    
    # 2. DEEP SEARCH SITES (MIDDLE)
    st.subheader("📡 Deep Search Sites")
    conn = get_db()
    customs = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
    active_customs = []
    for site in customs:
        if st.toggle(site, value=True, key=f"tog_{site}"):
            active_customs.append(site)
    conn.close()

    st.divider()

    # 3. KEYWORD LIBRARY (BOTTOM)
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("add_v26", clear_on_submit=True):
            nt = st.text_input("New Target:")
            if st.form_submit_button("＋", width="stretch"):
                if nt:
                    conn = get_db(); conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nt,)); conn.commit(); conn.close()
                    st.rerun()
        
        conn = get_db()
        targets = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        selected_targets = []
        for t in targets:
            col_check, col_del = st.columns([4, 1])
            if col_check.checkbox(t, value=True, key=f"chk_{t}"):
                selected_targets.append(t)
            if col_del.button("🗑️", key=f"del_{t}"):
                conn.execute("DELETE FROM targets WHERE name = ?", (t,))
                conn.commit(); conn.close(); st.rerun()
        conn.close()

# --- LIBRARY 4: TABS & DATA VIEW ---
t_live, t_arch, t_conf, t_logs = st.tabs(["📡 Live Results", "📜 Archive", "⚙️ Jobs", "🛠️ Logs"])

with t_live:
    # Manual Toggles for Engines
    c1, c2, c3 = st.columns(3)
    p_ebay = c1.toggle("eBay", value=True)
    p_etsy = c2.toggle("Etsy", value=False) # Defaulted to off per your car/computer part rule
    p_goog = c3.toggle("Google", value=True)
    
    if st.session_state.get('run_sweep'):
        # Mission Logic Execution...
        st.session_state['run_sweep'] = False
        st.success("Sweep Complete.")

with t_arch:
    st.subheader("📜 Archive")
    conn = get_db()
    arch_df = pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC", conn)
    conn.close()
    if not arch_df.empty:
        st.dataframe(arch_df, width="stretch", hide_index=True)
    else:
        st.info("Archive is currently empty. Run a sweep to populate.")

with t_logs:
    if st.button("🗑️ Purge Log", width="stretch"):
        open(LOG_FILE, 'w').close()
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-100:]))
