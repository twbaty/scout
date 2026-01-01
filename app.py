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
        "api_key": SERP_API_KEY,
        "ebay_domain": "ebay.com",
        "sort": "newly_listed"
    }
    logger.info(f"API Scouting eBay: {query}")
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        items = data.get("ebay_results", [])
        results = []
        for item in items[:10]:
            results.append({
                "target": query, "source": "eBay",
                "title": item.get("title"),
                "price": item.get("price", {}).get("raw", "N/A"),
                "url": item.get("link")
            })
        logger.info(f"eBay API found {len(results)} items.")
        return results
    except Exception as e:
        logger.error(f"eBay API Error: {e}")
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
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
init_db()

with st.sidebar:
    st.title("🛡️ Scout Control")
    
    # Manage Library
    st.subheader("Manage Library")
    new_t = st.text_input("New Target:", placeholder="e.g. OHP Patch")
    if st.button("➕ Add Target"):
        if new_t:
            conn = get_db_connection()
            conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_t,))
            conn.commit()
            conn.close()
            st.rerun()

    # Active Selection
    st.divider()
    conn = get_db_connection()
    all_targets = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
    conn.close()
    
    selected = []
    if all_targets:
        st.write("Targets to Scout:")
        for t in all_targets:
            if st.checkbox(t, value=True, key=f"t_{t}"):
                selected.append(t)
    
    st.divider()
    run_mission = st.button("🚀 EXECUTE SWEEP", use_container_width=True)
    
    if st.button("🗑️ Delete Selected"):
        conn = get_db_connection()
        for t in selected:
            conn.execute("DELETE FROM targets WHERE name = ?", (t,))
        conn.commit()
        conn.close()
        st.rerun()

# --- 6. MAIN DASHBOARD ---
st.title("Intelligence Dashboard")

# Top Metrics
conn = get_db_connection()
total_intel = pd.read_sql_query("SELECT count(*) as c FROM items", conn).iloc[0]['c']
conn.close()
st.metric("Total Intelligence Archive", total_intel)

tab1, tab2, tab3 = st.tabs(["📊 Live Intelligence", "📜 Archive", "🛠️ System Logs"])

with tab1:
    if run_mission:
        all_hits = []
        with st.status("Gathering Intel via Satellite...", expanded=True) as status:
            for target in selected:
                st.write(f"Searching: {target}")
                all_hits.extend(scout_ebay(target))
                all_hits.extend(scout_etsy(target))
                time.sleep(0.5)
            
            # Database Update
            conn = get_db_connection()
            for h in all_hits:
                try:
                    conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?, ?, ?, ?, ?)",
                                 (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass # Skip duplicates
            conn.commit()
            conn.close()
            status.update(label="✅ Sweep Complete!", state="complete")
        
        if all_hits:
            st.dataframe(pd.DataFrame(all_hits), use_container_width=True, hide_index=True,
                         column_config={"url": st.column_config.LinkColumn("View")})
        else:
            st.info("No items found. Check keywords or logs.")

with tab2:
    conn = get_db_connection()
    history = pd.read_sql_query("SELECT found_date as Date, source as Site, target as Target, title as Item, price as Price, url as Link FROM items ORDER BY found_date DESC", conn)
    conn.close()
    st.dataframe(history, column_config={"Link": st.column_config.LinkColumn("View")}, use_container_width=True, hide_index=True)

with tab3:
    if os.path.exists("scout.log"):
        with open("scout.log", "r") as f:
            st.code("".join(f.readlines()[-30:])) # Show last 30 lines
