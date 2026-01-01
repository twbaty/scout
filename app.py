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

# API Setup
try:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
except:
    st.error("Missing API Key in .streamlit/secrets.toml")
    st.stop()

# Logging Configuration
LOG_FILE = 'scout.log'
def setup_logger():
    # Remove existing handlers to avoid file locks
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        filename=LOG_FILE, 
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

logger = setup_logger()

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

# --- 3. SCOUTING LOGIC ---
def run_scout_mission(query, engine):
    url = "https://serpapi.com/search.json"
    params = {"engine": engine, "api_key": SERP_API_KEY}
    if engine == "ebay": params["_nkw"] = query
    elif engine == "etsy": params["q"] = query
    elif engine == "google_shopping": params["q"] = query
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        items = (data.get("organic_results") or data.get("ebay_results") or 
                 data.get("shopping_results") or data.get("etsy_results") or [])
        return [{"target": query, "source": engine.replace("_", " ").capitalize(), "title": i.get("title"), 
                 "price": i.get("price", {}).get("raw") or i.get("price", "N/A"), "url": i.get("link")} for i in items[:15]]
    except Exception as e:
        logger.error(f"API Error ({engine}): {e}")
        return []

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Scout Mission")
    conn = get_db_connection()
    targets_df = pd.read_sql_query("SELECT name FROM targets", conn)
    conn.close()
    
    st.write("### Target Selection")
    selected_targets = [t for t in targets_df['name'] if st.checkbox(t, value=True, key=f"sidebar_{t}")]
    
    st.divider()
    run_mission = st.button("🚀 EXECUTE SWEEP", use_container_width=True, type="primary")
    if st.button("🧹 Clear Live Tab"):
        st.session_state['last_results'] = []
        st.rerun()

# --- 5. THE TABS ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs([
    "📡 Live Intelligence", "📊 Dashboard", "📜 Archive", "⚙️ Configuration", "🛠️ Logs"
])

# TAB 1: LIVE INTELLIGENCE
with t_live:
    if run_mission and selected_targets:
        all_hits = []
        with st.status("Gathering Intel...", expanded=True) as status:
            for target in selected_targets:
                st.write(f"Scouting: **{target}**")
                if st.session_state.get('p_ebay', True): all_hits.extend(run_scout_mission(target, "ebay"))
                if st.session_state.get('p_etsy', True): all_hits.extend(run_scout_mission(target, "etsy"))
                if st.session_state.get('p_google', True): all_hits.extend(run_scout_mission(target, "google_shopping"))
                
                conn = get_db_connection()
                conn.execute("UPDATE targets SET last_run = ? WHERE name = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), target))
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
            status.update(label="✅ Mission Complete!", state="complete")

    if st.session_state.get('last_results'):
        st.dataframe(pd.DataFrame(st.session_state['last_results']), use_container_width=True, hide_index=True)
    else:
        st.info("Terminal Idle.")

# TAB 2: DASHBOARD
with t_dash:
    st.header("Intelligence Overview")
    conn = get_db_connection()
    df_all = pd.read_sql_query("SELECT source, target FROM items", conn)
    conn.close()
    
    if not df_all.empty:
        st.subheader("🎯 Intelligence Heatmap")
        st.write("Distribution of found items across **all active sources**:")
        heatmap_data = df_all.groupby(['target', 'source']).size().unstack(fill_value=0)
        st.table(heatmap_data)
    else:
        st.write("No data available for analysis yet.")

# TAB 3: ARCHIVE
with t_arch:
    st.header("The Intelligence Vault")
    
    conn = get_db_connection()
    # Get total count for the dataframe height logic
    total_count = conn.execute("SELECT count(*) FROM items").fetchone()[0]
    
    # Bottom-Right UI Logic
    arch_display_col, arch_ctrl_col = st.columns([4, 1])
    
    with arch_ctrl_col:
        depth = st.selectbox("View Depth:", [50, 100, 500, "All Records"], index=0)
    
    limit_clause = "" if depth == "All Records" else f"LIMIT {depth}"
    archive_df = pd.read_sql_query(f"SELECT found_date, source, target, title, price, url FROM items ORDER BY found_date DESC {limit_clause}", conn)
    conn.close()
    
    # height=600 gives a good scrollable area even with 'All Records'
    st.dataframe(
        archive_df, 
        column_config={"url": st.column_config.LinkColumn("Link")}, 
        use_container_width=True, 
        hide_index=True,
        height=min(600, (len(archive_df) * 35) + 40)
    )

# TAB 4: CONFIGURATION (As requested, keeping full library/ledger logic)
with t_conf:
    st.header("⚙️ Engine Room")
    st.subheader("🌐 Site Access")
    c1, c2, c3 = st.columns(3)
    c1.toggle("eBay", value=True, key="p_ebay")
    c2.toggle("Etsy", value=True, key="p_etsy")
    c3.toggle("Google Shopping", value=True, key="p_google")
    
    st.divider()
    st.subheader("📋 Mission Ledger")
    with st.expander("Register New Keyword"):
        r1, r2, r3 = st.columns([2, 1, 1])
        new_k = r1.text_input("Keyword:")
        new_f = r2.selectbox("Schedule:", ["Manual", "Every 12h", "Daily", "Mon/Wed/Fri", "Weekly", "Monthly"])
        if r3.button("Register", use_container_width=True):
            if new_k:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO targets (name, frequency) VALUES (?, ?)", (new_k, new_f))
                conn.commit(); conn.close()
                st.rerun()

    conn = get_db_connection()
    ledger = pd.read_sql_query("SELECT * FROM targets", conn)
    conn.close()
    for _, row in ledger.iterrows():
        l1, l2, l3, l4 = st.columns([2, 1, 1, 0.5])
        l1.write(f"**{row['name']}**")
        l2.info(f"⏱️ {row['frequency']}")
        l3.write(f"Last Run: {row['last_run'] if row['last_run'] else 'Never'}")
        if l4.button("🗑️", key=f"del_{row['name']}"):
            conn = get_db_connection()
            conn.execute("DELETE FROM targets WHERE name = ?", (row['name'],))
            conn.commit(); conn.close()
            st.rerun()

# TAB 5: LOGS
with t_logs:
    st.header("System Logs")
    if st.button("🗑️ Delete All Logs"):
        # Safely shut down logger to release the file
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)
        
        if os.path.exists(LOG_FILE):
            try:
                os.remove(LOG_FILE)
                st.success("Log file purged.")
                setup_logger() # Restart logger
                st.rerun()
            except Exception as e:
                st.error(f"Could not delete: {e}")
            
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-100:]), language="text")
