import streamlit as st
import pandas as pd
import sqlite3
import os
import logging
import requests
import time
from datetime import datetime

# --- 1. CORE SYSTEM CONFIG ---
st.set_page_config(page_title="SCOUT | Terminal", layout="wide")

# API & Logging Setup
try:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
except:
    st.error("Missing API Key in .streamlit/secrets.toml")
    st.stop()

logging.basicConfig(filename='scout.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 2. DATABASE ENGINE ---
def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS items 
                    (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                    target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS targets 
                    (name TEXT PRIMARY KEY, frequency TEXT DEFAULT 'Manual', last_run TIMESTAMP)''')
    
    # Migration Check
    cursor = conn.execute("PRAGMA table_info(targets)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'frequency' not in columns:
        conn.execute("ALTER TABLE targets ADD COLUMN frequency TEXT DEFAULT 'Manual'")
    if 'last_run' not in columns:
        conn.execute("ALTER TABLE targets ADD COLUMN last_run TIMESTAMP")
    conn.commit(); conn.close()

init_db()

# --- 3. SCOUTING ENGINE ---
def run_scout_mission(query, engine):
    url = "https://serpapi.com/search.json"
    params = {"engine": engine, "q" if engine == "etsy" else "_nkw": query, "api_key": SERP_API_KEY}
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        items = data.get("organic_results") or data.get("ebay_results") or data.get("etsy_results") or []
        return [{"target": query, "source": engine.capitalize(), "title": i.get("title"), 
                 "price": i.get("price", {}).get("raw") or i.get("price", "N/A"), "url": i.get("link")} for i in items[:15]]
    except Exception as e:
        logging.error(f"{engine} Error: {e}")
        return []

# --- 4. SIDEBAR (CLEAN MISSION LIST) ---
with st.sidebar:
    st.title("🛡️ Scout Mission")
    conn = get_db_connection()
    targets_df = pd.read_sql_query("SELECT name FROM targets", conn)
    conn.close()
    
    st.write("### Target Library")
    selected = []
    for t_name in targets_df['name']:
        if st.checkbox(t_name, value=True, key=f"active_{t_name}"):
            selected.append(t_name)
    
    st.divider()
    run_mission = st.button("🚀 EXECUTE SWEEP", use_container_width=True, type="primary")

# --- 5. THE TABS ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs([
    "📡 Live Intelligence", "📊 Dashboard", "📜 Archive", "⚙️ System Configuration", "🛠️ Logs"
])

# TAB 1: LIVE INTELLIGENCE
with t_live:
    if run_mission and selected:
        all_hits = []
        with st.status("Gathering Intel...", expanded=True) as status:
            for target in selected:
                st.write(f"Scanning: **{target}**")
                if st.session_state.get('p_ebay', True): all_hits.extend(run_scout_mission(target, "ebay"))
                if st.session_state.get('p_etsy', True): all_hits.extend(run_scout_mission(target, "etsy"))
                # Update last run time
                conn = get_db_connection()
                conn.execute("UPDATE targets SET last_run = ? WHERE name = ?", (datetime.now(), target))
                conn.commit(); conn.close()
                time.sleep(1)
            
            conn = get_db_connection()
            for h in all_hits:
                try:
                    conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?, ?, ?, ?, ?)", 
                                 (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass
            conn.commit(); conn.close()
            st.session_state['last_results'] = all_hits
            status.update(label="✅ Sweep Complete!", state="complete")
    
    if 'last_results' in st.session_state and st.session_state['last_results']:
        st.subheader("🚨 New Session Findings")
        st.dataframe(pd.DataFrame(st.session_state['last_results']), use_container_width=True, hide_index=True)
    else:
        st.info("No active findings. Execute a sweep from the sidebar.")

# TAB 2: DASHBOARD
with t_dash:
    st.header("Collection Analytics")
    conn = get_db_connection()
    total = pd.read_sql_query("SELECT count(*) as c FROM items", conn).iloc[0]['c']
    sources = pd.read_sql_query("SELECT source, count(*) as count FROM items GROUP BY source", conn)
    conn.close()
    
    m1, m2 = st.columns(2)
    m1.metric("Archive Total", total)
    m2.metric("Marketplaces Scanned", len(sources))
    st.bar_chart(sources.set_index('source'))

# TAB 3: ARCHIVE
with t_arch:
    st.header("The Intelligence Vault")
    conn = get_db_connection()
    history = pd.read_sql_query("SELECT found_date, source, target, title, price, url FROM items ORDER BY found_date DESC", conn)
    conn.close()
    st.dataframe(history, column_config={"url": st.column_config.LinkColumn("Link")}, use_container_width=True, hide_index=True)

# TAB 4: SYSTEM CONFIGURATION (THE MISSION LEDGER)
with t_conf:
    st.header("⚙️ Mission Ledger")
    
    # 1. Add New Target
    with st.expander("➕ Add New Intelligence Target", expanded=False):
        c1, c2, c3 = st.columns([2, 1, 1])
        new_k = c1.text_input("Keyword:")
        # "Tightened" frequency options
        new_f = c2.selectbox("Schedule:", ["Manual", "Every 12h", "Daily", "Mon/Wed/Fri", "Weekly", "Monthly"])
        if c3.button("Register Target", use_container_width=True):
            if new_k:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO targets (name, frequency) VALUES (?, ?)", (new_k, new_f))
                conn.commit(); conn.close()
                st.rerun()

    st.divider()

    # 2. Line-Item Mission Control
    st.subheader("📋 Active Mission Schedules")
    conn = get_db_connection()
    current_targets = pd.read_sql_query("SELECT * FROM targets", conn)
    conn.close()

    for _, row in current_targets.iterrows():
        # Line-item layout
        l_col1, l_col2, l_col3, l_col4 = st.columns([2, 1, 1, 0.5])
        l_col1.write(f"**{row['name']}**")
        l_col2.info(f"⏱️ {row['frequency']}")
        
        # Format the last run time
        last_val = row['last_run'] if row['last_run'] else "Never"
        l_col3.write(f"Last Run: {last_val}")
        
        if l_col4.button("🗑️", key=f"del_{row['name']}"):
            conn = get_db_connection()
            conn.execute("DELETE FROM targets WHERE name = ?", (row['name'],))
            conn.commit(); conn.close()
            st.rerun()

# TAB 5: LOGS
with t_logs:
    st.header("System Logs")
    if os.path.exists("scout.log"):
        with open("scout.log", "r") as f:
            st.code("".join(f.readlines()[-50:]), language="text")
