import streamlit as st
import pandas as pd
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import logging
import os

# --- 1. LOGGING SETUP ---
# Logs are stored in 'scout.log' in your local folder
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
    """Initializes the database and ensures all columns exist."""
    conn = get_db_connection()
    # Main Items Table
    conn.execute('''CREATE TABLE IF NOT EXISTS items 
                 (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    # Target Library Table
    conn.execute('''CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

# --- 3. SCRAPER ENGINES ---
def scrape_ebay(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
    }
    # Standard search URL
    url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=10"
    logger.info(f"Scouting eBay: {query}")
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # We search for the three most common listing containers used in 2025
        listings = soup.select('.s-item__info') or soup.select('.srp-results .s-item')
        
        results = []
        for i in listings:
            # eBay 2025 uses nested spans or specific 'header' tags for titles now
            title = i.select_one('.s-item__title span[role="heading"]') or \
                    i.select_one('.s-item__title') or \
                    i.select_one('h3.s-item__title')
            
            price = i.select_one('.s-item__price')
            link = i.select_one('.s-item__link')
            
            if title and price and link:
                clean_title = title.text.replace("New Listing", "").strip()
                # Skip the "Shop on eBay" result and empty headers
                if "Shop on eBay" in clean_title or not clean_title:
                    continue
                    
                results.append({
                    "target": query, 
                    "source": "eBay", 
                    "title": clean_title, 
                    "price": price.text.strip(), 
                    "url": link['href'].split('?')[0]
                })
        
        logger.info(f"eBay returned {len(results)} items after wide-net search.")
        return results[:10]
    except Exception as e:
        logger.error(f"eBay Error: {e}")
        return []
        

def scrape_etsy(query):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    url = f"https://www.etsy.com/search?q={query.replace(' ', '%20')}&ship_to=US"
    logger.info(f"Scouting Etsy: {query}")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Etsy Response Code: {resp.status_code}")
        soup = BeautifulSoup(resp.text, "html.parser")
        listings = soup.select('.v2-listing-card') 
        results = []
        for i in listings[:10]:
            title = i.select_one('h3')
            price = i.select_one('.currency-value')
            link = i.select_one('a.listing-link')
            if title and price and link:
                results.append({
                    "target": query, "source": "Etsy", 
                    "title": title.text.strip(), 
                    "price": f"${price.text}", "url": link['href'].split('?')[0]
                })
        logger.info(f"Etsy returned {len(results)} items.")
        return results
    except Exception as e:
        logger.error(f"Etsy Error: {e}")
        return []

# --- 4. APP CONFIGURATION & INITIALIZATION ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")
init_db() 

# --- 5. SIDEBAR: MISSION CONTROL ---
with st.sidebar:
    st.title("🛡️ Scout Control")
    
    # Manage Library
    st.subheader("Manage Library")
    new_target = st.text_input("Add New Target Keyword:", placeholder="e.g. OHP Patch")
    if st.button("➕ Add to Library"):
        if new_target:
            conn = get_db_connection()
            try:
                conn.execute("INSERT INTO targets (name) VALUES (?)", (new_target,))
                conn.commit()
                logger.info(f"Added '{new_target}' to library.")
            except sqlite3.IntegrityError:
                st.warning("Target already exists.")
            conn.close()
            st.rerun()

    st.divider()
    
    # Source & Selection
    st.subheader("Mission Setup")
    u_ebay = st.checkbox("eBay", value=True)
    u_etsy = st.checkbox("Etsy", value=True)
    
    # Fetch Current Library for Checkboxes
    conn = get_db_connection()
    targets_df = pd.read_sql_query("SELECT name FROM targets", conn)
    targets = targets_df['name'].tolist()
    conn.close()
    
    selected_targets = []
    if targets:
        st.write("Select Targets to Scout:")
        for t in targets:
            if st.checkbox(t, value=True, key=f"t_{t}"):
                selected_targets.append(t)
    else:
        st.info("Library is empty. Add a target above.")
            
    st.divider()
    
    # Run Sweep
    run_sweep = st.button(f"🚀 Scout {len(selected_targets)} Targets", use_container_width=True)
    
    # Delete Logic
    if st.button("🗑️ Delete Selected from Library"):
        conn = get_db_connection()
        for t in selected_targets:
            conn.execute("DELETE FROM targets WHERE name = ?", (t,))
        conn.commit()
        conn.close()
        logger.info(f"Deleted {len(selected_targets)} targets.")
        st.rerun()

# --- 6. MAIN DASHBOARD ---
st.title("Scout Intelligence Terminal")

# Persistent Metrics
conn = get_db_connection()
try:
    total_items = pd.read_sql_query("SELECT count(*) as c FROM items", conn).iloc[0]['c']
    new_today = pd.read_sql_query("SELECT count(*) as c FROM items WHERE found_date > datetime('now', '-1 day')", conn).iloc[0]['c']
except:
    total_items = 0
    new_today = 0
conn.close()

col1, col2, col3 = st.columns(3)
col1.metric("90-Day Archive", total_items)
col2.metric("New Finds (Today)", new_today)
col3.metric("System Status", "Live/Operational")

tab1, tab2, tab3 = st.tabs(["📊 Live Intelligence", "📜 Archive History", "🛠️ System Logs"])

with tab1:
    if run_sweep:
        if not selected_targets:
            st.warning("Please select at least one target keyword.")
        else:
            all_hits = []
            with st.status("Executing Multi-Site Sweep...", expanded=True) as status:
                for target in selected_targets:
                    if u_ebay:
                        st.write(f"Searching eBay: **{target}**")
                        all_hits.extend(scrape_ebay(target))
                    if u_etsy:
                        st.write(f"Searching Etsy: **{target}**")
                        all_hits.extend(scrape_etsy(target))
                    time.sleep(1) # Polite delay to avoid IP blocks
                
                # Save Findings to DB
                conn = get_db_connection()
                new_entries = 0
                for h in all_hits:
                    try:
                        conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?, ?, ?, ?, ?)",
                                     (h['target'], h['source'], h['title'], h['price'], h['url']))
                        new_entries += 1
                    except sqlite3.IntegrityError:
                        pass # Duplicate listing, ignore
                conn.commit()
                conn.close()
                status.update(label=f"✅ Sweep Complete! Found {new_entries} new items.", state="complete")
            
            if all_hits:
                st.subheader("Current Session Intelligence")
                st.dataframe(pd.DataFrame(all_hits), use_container_width=True, hide_index=True,
                             column_config={"url": st.column_config.LinkColumn("View Listing")})
            else:
                st.info("No listings found for current selection. Try broader keywords.")
    else:
        st.info("Configure your mission in the sidebar and hit 'Scout' to begin.")

with tab2:
    st.subheader("Historical Intelligence Archive")
    conn = get_db_connection()
    try:
        history = pd.read_sql_query("SELECT found_date as Date, source as Site, target as Target, title as Item, price as Cost, url as Link FROM items ORDER BY found_date DESC", conn)
        st.dataframe(history, column_config={"Link": st.column_config.LinkColumn("View")}, use_container_width=True, hide_index=True)
    except:
        st.write("Archive is currently empty.")
    conn.close()

with tab3:
    st.subheader("Backend Activity Log")
    if os.path.exists("scout.log"):
        with open("scout.log", "r") as f:
            log_lines = f.readlines()
            # Display last 50 lines of log
            st.code("".join(log_lines[-50:]))
    else:
        st.write("No log file found yet.")
    
    if st.button("🗑️ Clear Log File"):
        if os.path.exists("scout.log"):
            os.remove("scout.log")
            st.rerun()
