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
        # Handle the specific 'organic_results' key you found earlier
        items = data.get("organic_results") or data.get("ebay_results") or data.get("etsy_results") or []
        return [{"target": query, "source": engine.capitalize(), "title": i.get("title"), "price": i.get("price", {}).get("raw") or i.get("price"), "url": i.get("link")} for i in items[:15]]
    except Exception as e:
        logger.error(f"{engine} Error: {e}")
        return []

# --- 4. SIDEBAR (MISSION CONTROL) ---
with st.sidebar:
    st.title("🛡️ Scout Mission")
    
    with st.expander("📚 Library Management", expanded=False):
        new_t = st.text_input("New Keyword:")
        if st.button("➕ Add"):
            if new_t:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_t,))
                conn.commit(); conn.close()
                st.rerun()
        
        st.divider()
        conn = get_db_connection()
        all_targets = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
        conn.close()
        target_to_del = st.selectbox("Remove:", ["-- Select --"] + all_targets)
        if st.button("🗑️ Delete"):
            if target_to_del != "-- Select --":
                conn = get_db_connection()
                conn.execute("DELETE FROM targets WHERE name = ?", (target_to_del,))
                conn.commit(); conn.close()
                st.rerun()

    st.divider()
    st.write("Active Targets:")
    selected = [t for t in all_targets if st.checkbox(t, value=True, key=f"active_{t}")]
    
    st.divider()
    run_mission = st.button("🚀 EXECUTE SWEEP", use_container_width=True, type="primary")

# --- 5. THE TABS (MAIN INTERFACE) ---
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
            
            # Save to DB
            conn = get_db_connection()
            for h in all_hits:
                try:
                    conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?, ?, ?, ?, ?)", (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass
            conn.commit(); conn.close()
            status.update(label="✅ Sweep Complete!", state="complete")
        
        if all_hits:
            st.subheader("🚨 New Findings Found")
            st.dataframe(pd.DataFrame(all_hits), use_container_width=True, hide_index=True)
    else:
        st.info("No active session. Toggle targets in the sidebar and hit 'Execute Sweep'.")

# TAB 2: DASHBOARD
with t_dash:
    st.header("Collection Analytics")
    conn = get_db_connection()
    total = pd.read_sql_query("SELECT count(*) as c FROM items", conn).iloc[0]['c']
    sources = pd.read_sql_query("SELECT source, count(*) as count FROM items GROUP BY source", conn)
    conn.close()
    
    m1, m2 = st.columns(2)
    m1.metric("Items in Archive", total)
    m2.metric("Marketplaces", len(sources))
    st.bar_chart(sources.set_index('source'))

# TAB 3: ARCHIVE
with t_arch:
    st.header("Historical Intel")
    conn = get_db_connection()
    history = pd.read_sql_query("SELECT found_date, source, target, title, price, url FROM items ORDER BY found_date DESC", conn)
    conn.close()
    st.dataframe(history, column_config={"url": st.column_config.LinkColumn("Link")}, use_container_width=True, hide_index=True)

# TAB 4: CONFIG
with t_conf:
    st.header("Mission Preferences")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Site Toggles")
        st.toggle("Search eBay", value=True, key="p_ebay")
        st.toggle("Search Etsy", value=True, key="p_etsy")
    with c2:
        st.subheader("Search Logic")
        st.select_slider("Mission Frequency", options=["Manual", "1h", "6h", "Daily"], key="p_freq")

# TAB 5: LOGS
with t_logs:
    st.header("System Logs")
    if os.path.exists("scout.log"):
        with open("scout.log", "r") as f:
            st.code("".join(f.readlines()[-50:]), language="text")
