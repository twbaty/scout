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
logging.basicConfig(
    filename='scout.log', 
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 2. DATABASE ENGINE ---
def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    # Archive Table
    conn.execute('''CREATE TABLE IF NOT EXISTS items 
                    (id INTEGER PRIMARY KEY, 
                     found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                     target TEXT, 
                     source TEXT, 
                     title TEXT, 
                     price TEXT, 
                     url TEXT UNIQUE)''')
    # Targets/Library Table
    conn.execute('''CREATE TABLE IF NOT EXISTS targets 
                    (name TEXT PRIMARY KEY, 
                     frequency TEXT DEFAULT 'Manual', 
                     last_run TIMESTAMP)''')
    
    # Migration Check: Ensure columns exist for older DBs
    cursor = conn.execute("PRAGMA table_info(targets)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'frequency' not in columns:
        conn.execute("ALTER TABLE targets ADD COLUMN frequency TEXT DEFAULT 'Manual'")
    if 'last_run' not in columns:
        conn.execute("ALTER TABLE targets ADD COLUMN last_run TIMESTAMP")
    conn.commit()
    conn.close()

init_db()

# --- 3. SCOUTING LOGIC ---
def run_scout_mission(query, engine):
    url = "https://serpapi.com/search.json"
    params = {
        "engine": engine,
        "api_key": SERP_API_KEY
    }
    # Handle engine-specific parameter names
    if engine == "ebay":
        params["_nkw"] = query
    elif engine == "etsy":
        params["q"] = query
    elif engine == "google_shopping":
        params["q"] = query
        params["direct_link"] = "true"

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        # Pull from the correct results key
        items = (data.get("organic_results") or 
                 data.get("ebay_results") or 
                 data.get("shopping_results") or 
                 data.get("etsy_results") or [])
        
        results = []
        for i in items[:15]:
            results.append({
                "target": query,
                "source": engine.replace("_", " ").capitalize(),
                "title": i.get("title"),
                "price": i.get("price", {}).get("raw") or i.get("price", "N/A"),
                "url": i.get("link")
            })
        return results
    except Exception as e:
        logger.error(f"API Failure on {engine} for {query}: {e}")
        return []

# --- 4. SIDEBAR (MISSION CONTROL) ---
with st.sidebar:
    st.title("🛡️ Scout Mission")
    
    conn = get_db_connection()
    targets_df = pd.read_sql_query("SELECT name FROM targets", conn)
    conn.close()
    
    st.write("### Target Selection")
    selected_targets = []
    for t_name in targets_df['name']:
        if st.checkbox(t_name, value=True, key=f"active_{t_name}"):
            selected_targets.append(t_name)
    
    st.divider()
    run_mission = st.button("🚀 EXECUTE SWEEP", use_container_width=True, type="primary")
    
    if st.button("🧹 Clear Live Results"):
        if 'last_results' in st.session_state:
            st.session_state['last_results'] = []
            st.rerun()

# --- 5. THE MAIN INTERFACE (TABS) ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs([
    "📡 Live Intelligence", 
    "📊 Dashboard", 
    "📜 Archive", 
    "⚙️ System Configuration", 
    "🛠️ Logs"
])

# TAB 1: LIVE INTELLIGENCE
with t_live:
    if run_mission and selected_targets:
        all_hits = []
        with st.status("Gathering Intel...", expanded=True) as status:
            for target in selected_targets:
                st.write(f"Scouting: **{target}**")
                
                # Check site toggles from Config tab
                if st.session_state.get('p_ebay', True):
                    all_hits.extend(run_scout_mission(target, "ebay"))
                if st.session_state.get('p_etsy', True):
                    all_hits.extend(run_scout_mission(target, "etsy"))
                if st.session_state.get('p_google', True):
                    all_hits.extend(run_scout_mission(target, "google_shopping"))
                
                # Timestamp the run
                conn = get_db_connection()
                conn.execute("UPDATE targets SET last_run = ? WHERE name = ?", 
                             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), target))
                conn.commit(); conn.close()
                time.sleep(1) # API Courtesy delay
            
            # Save new items to DB
            conn = get_db_connection()
            for h in all_hits:
                try:
                    conn.execute("""INSERT INTO items (target, source, title, price, url) 
                                 VALUES (?, ?, ?, ?, ?)""", 
                                 (h['target'], h['source'], h['title'], h['price'], h['url']))
                except:
                    pass # Skip duplicates
            conn.commit(); conn.close()
            
            st.session_state['last_results'] = all_hits
            status.update(label="✅ Mission Complete!", state="complete")

    if 'last_results' in st.session_state and st.session_state['last_results']:
        st.subheader("🚨 New Session Findings")
        st.dataframe(pd.DataFrame(st.session_state['last_results']), use_container_width=True, hide_index=True)
    else:
        st.info("Terminal Idle. Use sidebar to execute mission.")

# TAB 2: DASHBOARD
with t_dash:
    st.header("Collection Analytics")
    conn = get_db_connection()
    total_items = pd.read_sql_query("SELECT count(*) as c FROM items", conn).iloc[0]['c']
    by_source = pd.read_sql_query("SELECT source, count(*) as count FROM items GROUP BY source", conn)
    by_target = pd.read_sql_query("SELECT target, count(*) as count FROM items GROUP BY target", conn)
    conn.close()
    
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Items in Vault", total_items)
    col_m2.metric("Active Marketplaces", len(by_source))
    
    st.subheader("Hits by Keyword")
    st.bar_chart(by_target.set_index('target'))

# TAB 3: ARCHIVE
with t_arch:
    st.header("The Intelligence Vault")
    conn = get_db_connection()
    archive_df = pd.read_sql_query("SELECT found_date, source, target, title, price, url FROM items ORDER BY found_date DESC", conn)
    conn.close()
    st.dataframe(
        archive_df, 
        column_config={"url": st.column_config.LinkColumn("Listing URL")},
        use_container_width=True, 
        hide_index=True
    )

# TAB 4: SYSTEM CONFIGURATION
with t_conf:
    st.header("⚙️ Engine Room")
    
    # Part 1: Marketplace Toggles
    st.subheader("🌐 Global Site Access")
    c_site1, c_site2, c_site3 = st.columns(3)
    c_site1.toggle("Search eBay", value=True, key="p_ebay")
    c_site2.toggle("Search Etsy", value=True, key="p_etsy")
    c_site3.toggle("Search Google Shopping", value=True, key="p_google")
    
    st.divider()

    # Part 2: Register New Item
    st.subheader("➕ Target Registration")
    with st.expander("Register New Keyword"):
        reg_col1, reg_col2, reg_col3 = st.columns([2, 1, 1])
        new_keyword = reg_col1.text_input("Intelligence Target:")
        new_freq = reg_col2.selectbox("Schedule:", ["Manual", "Every 12h", "Daily", "Mon/Wed/Fri", "Weekly", "Monthly"])
        if reg_col3.button("Register", use_container_width=True):
            if new_keyword:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO targets (name, frequency) VALUES (?, ?)", (new_keyword, new_freq))
                conn.commit(); conn.close()
                st.rerun()

    st.divider()

    # Part 3: Mission Ledger (Manage existing items)
    st.subheader("📋 Active Mission Ledger")
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

    st.divider()
    if st.button("🧨 Wipe Database Items"):
        if st.checkbox("Confirm wipe of all archived findings?"):
            conn = get_db_connection()
            conn.execute("DELETE FROM items")
            conn.commit(); conn.close()
            st.warning("Archive Purged.")

# TAB 5: LOGS
with t_logs:
    st.header("System Logs")
    if os.path.exists("scout.log"):
        with open("scout.log", "r") as f:
            log_data = f.readlines()
            st.code("".join(log_data[-50:]), language="text")
    else:
        st.write("No log file found.")
