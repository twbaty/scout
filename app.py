import streamlit as st
import pandas as pd
import sqlite3
import requests
import time
import os
import logging

# --- 1. SECURE KEY REFERENCE ---
# This looks for the key in C:\Users\Tom Baty\code\scout\.streamlit\secrets.toml
try:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
except Exception as e:
    st.error("Missing API Key! Please check your .streamlit/secrets.toml file.")
    st.stop()

# --- 2. LOGGING SETUP ---
logging.basicConfig(
    filename='scout.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 3. DATABASE ENGINE ---
def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS items 
                 (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

# --- 4. API ENGINES (SERPAPI) ---
def scout_ebay(query):
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "ebay",
        "_nkw": query,
        "api_key": SERP_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        # FIX: eBay results in SerpApi are often under 'organic_results'
        items = data.get("organic_results") or data.get("ebay_results") or []
        
        results = []
        for i in items[:15]:
            results.append({
                "target": query, "source": "eBay",
                "title": i.get("title"),
                "price": i.get("price", {}).get("raw", "N/A"),
                "url": i.get("link")
            })
        return results
    except Exception as e:
        logger.error(f"eBay Mapping Error: {e}")
        return []

def scout_etsy(query):
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "etsy",
        "q": query,
        "api_key": SERP_API_KEY
    }
    logger.info(f"API Scouting Etsy: {query}")
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        items = data.get("etsy_results", [])
        results = []
        for item in items[:10]:
            results.append({
                "target": query, "source": "Etsy",
                "title": item.get("title"),
                "price": item.get("price", "N/A"),
                "url": item.get("link")
            })
        logger.info(f"Etsy API found {len(results)} items.")
        return results
    except Exception as e:
        logger.error(f"Etsy API Error: {e}")
        return []

# --- 5. APP INTERFACE ---
st.set_page_config(page_title="SCOUT | Terminal V3", layout="wide")
init_db()

# Navigation Tabs
tab_dash, tab_settings = st.tabs(["📊 Intelligence Dashboard", "⚙️ System Configuration"])

with tab_settings:
    st.header("Terminal Preferences")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Marketplace Access")
        st.toggle("Search eBay", value=True, key="pref_ebay")
        st.toggle("Search Etsy", value=True, key="pref_etsy")
        st.toggle("Search Google Shopping", value=True, key="pref_google")
        
        st.divider()
        st.subheader("🕵️ Mission Scheduler")
        st.select_slider("Search Frequency", options=["Manual Only", "Every 1hr", "Every 6hrs", "Daily"], key="pref_freq")
        st.caption("Note: Automated background runs require a dedicated server (like Streamlit Cloud or a local PC always on).")

    with col_b:
        st.subheader("Search Parameters")
        st.slider("Results per target:", 5, 50, 15, key="pref_depth")
        st.checkbox("Include 'Sold' Items (eBay only)", value=False, key="pref_sold")

with tab_dash:
    # --- TOP SECTION: ACTION BAR ---
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
            
            st.write("---")
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
        run_mission = st.button("🚀 EXECUTE SWEEP", use_container_width=True, type="primary")

    # --- MAIN DASHBOARD: THE THREE-COLUMN ROW ---
    st.title("Intelligence Dashboard")
    
    # 1. LIVE RESULTS (Top Priority)
    if run_mission:
        all_hits = []
        with st.status("Gathering Intel...", expanded=True) as status:
            # (Your API calling logic remains the same here)
            # ... all_hits.extend(scout_ebay(target)) etc ...
            status.update(label="✅ Sweep Complete!", state="complete")
        
        if all_hits:
            st.subheader("🚨 New Findings")
            st.dataframe(pd.DataFrame(all_hits), use_container_width=True, hide_index=True)
            st.divider()

    # 2. THE DATA ROW (The "One Row" View)
    col1, col2, col3 = st.columns([2, 2, 1]) # Adjust ratios as needed

    with col1:
        st.subheader("📊 Live Intel")
        st.caption("Most recent hits across all active targets.")
        # Logic to show only the last 20 hits
        conn = get_db_connection()
        live_data = pd.read_sql_query("SELECT source, title, price, url FROM items ORDER BY found_date DESC LIMIT 20", conn)
        conn.close()
        st.dataframe(live_data, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("📜 Archive")
        st.caption("Full history of every item ever scouted.")
        conn = get_db_connection()
        archive_data = pd.read_sql_query("SELECT target, title, price FROM items ORDER BY found_date DESC", conn)
        conn.close()
        st.dataframe(archive_data, use_container_width=True, hide_index=True)

    with col3:
        st.subheader("🛠️ Logs")
        st.caption("System health & API status.")
        if os.path.exists("scout.log"):
            with open("scout.log", "r") as f:
                log_lines = f.readlines()[-15:] # Show last 15 lines
                st.code("".join(log_lines), language="text")
