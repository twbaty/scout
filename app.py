import streamlit as st
import pandas as pd
import sqlite3
import os
import logging
import requests
import time
from datetime import datetime, timedelta

# --- 1. CORE SYSTEM CONFIG ---
st.set_page_config(page_title="SCOUT | Terminal", layout="wide")

# API Setup
try:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
except:
    st.error("API Key missing in .streamlit/secrets.toml")
    st.stop()

# Logging
logging.basicConfig(filename='scout.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. DATABASE ENGINE (Updated for Scheduling) ---
def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    # Items Table
    conn.execute('''CREATE TABLE IF NOT EXISTS items 
                    (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                    target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    # Targets Table (Updated with schedule columns)
    conn.execute('''CREATE TABLE IF NOT EXISTS targets 
                    (name TEXT PRIMARY KEY, frequency TEXT DEFAULT 'Manual', last_run TIMESTAMP)''')
    conn.commit(); conn.close()

init_db()

# --- 3. SCOUTING ENGINES ---
def run_scout_mission(query, engine):
    url = "https://serpapi.com/search.json"
    params = {
        "engine": engine,
        "q" if engine == "etsy" else "_nkw": query,
        "api_key": SERP_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        items = data.get("organic_results") or data.get("ebay_results") or data.get("etsy_results") or []
        return [{"target": query, "source": engine.capitalize(), "title": i.get("title"), 
                 "price": i.get("price", {}).get("raw") or i.get("price", "N/A"), "url": i.get("link")} for i in items[:15]]
    except Exception as e:
        logger.error(f"{engine} Error: {e}")
        return []

# --- 4. SIDEBAR (MISSION CONTROL) ---
with st.sidebar:
    st.title("🛡️ Scout Mission")
    conn = get_db_connection()
    targets_df = pd.read_sql_query("SELECT * FROM targets", conn)
    conn.close()
    
    st.write("### Active Targets")
    selected = []
    for index, row in targets_df.iterrows():
        if st.checkbox(f"{row['name']} ({row['frequency']})", value=True, key=f"active_{row['name']}"):
            selected.append(row['name'])
    
    st.divider()
    run_mission = st.button("🚀 EXECUTE SWEEP", use_container_width=True, type="primary")

# --- 5. THE TABS (THE COMMAND CENTER) ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs([
    "📡 Live Intelligence", "📊 Intelligence Dashboard", "📜 Archive", "⚙️ System Configuration", "🛠️ Logs"
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

# TAB 4: SYSTEM CONFIGURATION
with t_conf:
    st.header("Advanced Engine Room")
    
    col_lib, col_settings = st.columns(2)
    
    with col_lib:
        st.subheader("📚 Per-Item Scheduling")
        with st.form("add_keyword_form"):
            new_t = st.text_input("New Target Keyword:")
            new_f = st.selectbox("Frequency:", ["Manual", "Hourly", "Daily", "Weekly", "Monthly"])
            if st.form_submit_button("➕ Add to Library"):
                if new_t:
                    conn = get_db_connection()
                    conn.execute("INSERT OR IGNORE INTO targets (name, frequency) VALUES (?, ?)", (new_t, new_f))
                    conn.commit(); conn.close()
                    st.rerun()
        
        st.divider()
        target_to_del = st.selectbox("Remove from Library:", ["-- Select --"] + targets_df['name'].tolist())
        if st.button("🗑️ Delete Selected"):
            if target_to_del != "-- Select --":
                conn = get_db_connection()
                conn.execute("DELETE FROM targets WHERE name = ?", (target_to_del,))
                conn.commit(); conn.close()
                st.rerun()

    with col_settings:
        st.subheader("🔧 Site Controls")
        st.toggle("Search eBay", value=True, key="p_ebay")
        st.toggle("Search Etsy", value=True, key="p_etsy")
        st.toggle("Search Google Shopping", value=True, key="p_google")
        
        st.divider()
        if st.button("🧨 Wipe Database"):
            if st.checkbox("Confirm Wipe?"):
                conn = get_db_connection()
                conn.execute("DELETE FROM items"); conn.commit(); conn.close()
                st.warning("Database Cleared.")

# TAB 5: LOGS
with t_logs:
    st.header("System Logs")
    if os.path.exists("scout.log"):
        with open("scout.log", "r") as f:
            st.code("".join(f.readlines()[-50:]), language="text")
