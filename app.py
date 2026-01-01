import streamlit as st
import pandas as pd
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import logging

# --- 1. LOGGING CONFIGURATION ---
# This creates a file 'scout.log' that tracks everything behind the scenes.
logging.basicConfig(
    filename='scout.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 2. APP CONFIGURATION ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

# --- 3. SCRAPER ENGINES (Refined) ---
def scrape_ebay(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=10"
    
    logger.info(f"Initiating eBay search for: {query}")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        logger.info(f"eBay Response: {resp.status_code} | Length: {len(resp.text)}")
        
        soup = BeautifulSoup(resp.text, "html.parser")
        # Broad selector to catch eBay's varying layouts
        listings = soup.select('.s-item__info')
        
        results = []
        for i in listings:
            title = i.select_one('.s-item__title')
            price = i.select_one('.s-item__price')
            link = i.select_one('.s-item__link')
            
            if title and price and link and "Shop on eBay" not in title.text:
                results.append({
                    "target": query, "source": "eBay", 
                    "title": title.text.replace("New Listing", "").strip(), 
                    "price": price.text.strip(), "url": link['href'].split('?')[0]
                })
        
        logger.info(f"eBay found {len(results)} items for {query}")
        return results[:10]
    except Exception as e:
        logger.error(f"eBay Scrape Failed: {e}")
        return []

def scrape_etsy(query):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    # Etsy often requires the ship_to parameter to show results consistently
    url = f"https://www.etsy.com/search?q={query.replace(' ', '%20')}&ship_to=US"
    
    logger.info(f"Initiating Etsy search for: {query}")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Etsy Response: {resp.status_code} | Length: {len(resp.text)}")
        
        soup = BeautifulSoup(resp.text, "html.parser")
        # Updated Etsy selector for 2025
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
        
        logger.info(f"Etsy found {len(results)} items for {query}")
        return results
    except Exception as e:
        logger.error(f"Etsy Scrape Failed: {e}")
        return []

# --- 4. SIDEBAR MISSION CONTROL ---
init_db()
with st.sidebar:
    st.title("🛡️ Scout Control")
    
    # Section: Manage Library
    st.subheader("Manage Targets")
    new_target = st.text_input("Add Target:", placeholder="e.g. Texas Ranger")
    if st.button("➕ Add to Library"):
        if new_target:
            conn = get_db_connection()
            try:
                conn.execute("INSERT INTO targets (name) VALUES (?)", (new_target,))
                conn.commit()
            except: st.warning("Already in library.")
            conn.close()
            st.rerun()

    st.divider()

    # Section: Source Selection
    st.subheader("Search Sources")
    col_a, col_b = st.columns(2)
    with col_a: use_ebay = st.checkbox("eBay", value=True)
    with col_b: use_etsy = st.checkbox("Etsy", value=True)

    st.divider()

    # Section: Target Selection (Checkboxes)
    st.subheader("Active Targets")
    conn = get_db_connection()
    all_targets = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
    conn.close()

    selected_targets = []
    for t in all_targets:
        if st.checkbox(t, value=True, key=f"cb_{t}"):
            selected_targets.append(t)

    st.divider()
    
    # Action Buttons
    if st.button(f"🚀 Scout {len(selected_targets)} Targets", use_container_width=True):
        st.session_state.run_sweep = True
    else:
        st.session_state.run_sweep = False

    if st.button("🗑️ Delete Selected"):
        conn = get_db_connection()
        for t in selected_targets:
            conn.execute("DELETE FROM targets WHERE name = ?", (t,))
        conn.commit()
        conn.close()
        st.rerun()

# --- 5. MAIN DASHBOARD ---
st.title("Scout Intelligence Terminal")

# Top Metrics
conn = get_db_connection()
total_count = pd.read_sql_query("SELECT count(*) as count FROM items", conn).iloc[0]['count']
new_today = pd.read_sql_query("SELECT count(*) as count FROM items WHERE found_date > datetime('now', '-1 day')", conn).iloc[0]['count']
conn.close()

m1, m2, m3 = st.columns(3)
m1.metric("90-Day Archive", total_count)
m2.metric("New Finds (24h)", new_today)
m3.metric("System Status", "Live")

tab1, tab2 = st.tabs(["📊 Live Intelligence", "📜 Intelligence Archive"])

with tab1:
    if st.session_state.get('run_sweep'):
        all_found = []
        with st.status("Gathering Intelligence...", expanded=True) as status:
            for target in selected_targets:
                if use_ebay:
                    st.write(f"eBay: {target}")
                    all_found.extend(scrape_ebay(target))
                if use_etsy:
                    st.write(f"Etsy: {target}")
                    all_found.extend(scrape_etsy(target))
                time.sleep(1) # Safety delay
            
            # Database Update
            conn = get_db_connection()
            for item in all_found:
                try:
                    conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?, ?, ?, ?, ?)",
                                 (item['target'], item['source'], item['title'], item['price'], item['url']))
                except: pass
            conn.commit()
            conn.close()
            status.update(label="✅ Sweep Complete!", state="complete")

        if all_found:
            st.dataframe(pd.DataFrame(all_found), use_container_width=True, hide_index=True,
                         column_config={"url": st.column_config.LinkColumn("View Listing")})
        else:
            st.info("No listings found for current selection.")
    else:
        st.info("Select targets and sites in the sidebar to begin.")

with tab2:
    conn = get_db_connection()
    history = pd.read_sql_query("SELECT found_date as Date, source as Source, target as Target, title as Item, price as Cost, url as Link FROM items ORDER BY found_date DESC", conn)
    conn.close()
    st.dataframe(history, column_config={"Link": st.column_config.LinkColumn("View")}, use_container_width=True, hide_index=True)
