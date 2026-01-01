import streamlit as st
import pandas as pd
import sqlite3
import os
import logging
import requests
import time

# --- 1. CORE SYSTEM CONFIG ---
st.set_page_config(page_title="SCOUT | Terminal", layout="wide")

# API Setup
try:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
except:
    st.error("API Key missing in secrets.toml")
    st.stop()

# Logging
logging.basicConfig(filename='scout.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. DATABASE ENGINE ---
def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)')
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
        # Ensure we check the right keys for results
        items = data.get("organic_results") or data.get("ebay_results") or data.get("etsy_results") or []
        return [{"target": query, "source": engine.capitalize(), "title": i.get("title"), "price": i.get("price", {}).get("raw") or i.get("price"), "url": i.get("link")} for i in items[:15]]
    except Exception as e:
        logger.error(f"{engine} Error: {e}")
        return []

# --- 4. SIDEBAR (MISSION CONTROL) ---
with st.sidebar:
    st.title("🛡️ Scout Mission")
    
    # Quick Status
    conn = get_db_connection()
    all_targets = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
    conn.close()
    
    st.write("### Active Targets")
    selected = [t for t in all_targets if st.checkbox(t, value=True, key=f"active_{t}")]
    
    st.divider()
    run_mission = st.button("🚀 EXECUTE SWEEP", use_container_width=True, type="primary")
    
    if st.button("🧹 Clear Live Results"):
        st.session_state['last_results'] = []
        st.rerun()

# --- 5. THE TABS (THE COMMAND CENTER) ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs([
    "📡 Live Intelligence", 
    "📊 Intelligence Dashboard", 
    "📜 Archive", 
    "⚙️ System Configuration", 
    "🛠️ Logs"
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
    targets_stats = pd.read_sql_query("SELECT target, count(*) as count FROM items GROUP BY target", conn)
    conn.close()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Archive Total", total)
    m2.metric("Marketplaces", len(sources))
    m3.metric("Unique Keywords", len(targets_stats))
    
    st.write("### Hits by Target")
    st.bar_chart(targets_stats.set_index('target'))

# TAB 4: SYSTEM CONFIGURATION (RE-POWERED)
with t_conf:
    st.header("Engine Room & Library")
    
    col_lib, col_settings = st.columns(2)
    
    with col_lib:
        st.subheader("📚 Library Management")
        new_t = st.text_input("Add New Target Keyword:", placeholder="e.g. Vintage Cowboy Spurs")
        if st.button("➕ Add to Library"):
            if new_t:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_t,))
                conn.commit(); conn.close()
                st.success(f"Added '{new_t}'")
                st.rerun()
        
        st.divider()
        target_to_del = st.selectbox("Remove from Library:", ["-- Select --"] + all_targets)
        if st.button("🗑️ Delete Selected"):
            if target_to_del != "-- Select --":
                conn = get_db_connection()
                conn.execute("DELETE FROM targets WHERE name = ?", (target_to_del,))
                conn.commit(); conn.close()
                st.rerun()

    with col_settings:
        st.subheader("🔧 System Preferences")
        st.toggle("Search eBay", value=True, key="p_ebay")
        st.toggle("Search Etsy", value=True, key="p_etsy")
        st.toggle("Search Google Shopping", value=True, key="p_google")
        
        st.divider()
        st.subheader("⏰ Mission Scheduler")
        st.select_slider("Automated Sweep Frequency", options=["Manual Only", "1h", "6h", "Daily"], key="p_freq")
        
        if st.button("🧨 Wipe Intelligence Database"):
            if st.checkbox("Confirm Complete Wipe?"):
                conn = get_db_connection()
                conn.execute("DELETE FROM items")
                conn.commit(); conn.close()
                st.warning("Database Cleared.")

# TAB 3: ARCHIVE
with t_arch:
    st.header("The Intelligence Vault")
    conn = get_db_connection()
    history = pd.read_sql_query("SELECT found_date, source, target, title, price, url FROM items ORDER BY found_date DESC", conn)
    conn.close()
    st.dataframe(history, column_config={"url": st.column_config.LinkColumn("Link")}, use_container_width=True, hide_index=True)

# TAB 5: LOGS
with t_logs:
    st.header("System Logs")
    if os.path.exists("scout.log"):
        with open("scout.log", "r") as f:
            st.code("".join(f.readlines()[-50:]), language="text")
