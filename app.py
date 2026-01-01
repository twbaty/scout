import streamlit as st
import pandas as pd
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

# Styling
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 2rem; color: #58a6ff; }
    .stDataFrame { border: 1px solid #30363d; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE ENGINE ---
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

# --- 3. SCRAPER ENGINES ---
def scrape_ebay(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }
    
    # Using a slightly different URL structure that is harder for eBay to block
    url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=10"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        # DEBUG: If this is 403, eBay is blocking you.
        if response.status_code != 200:
            st.warning(f"eBay returned Status {response.status_code}. They might be blocking automated access.")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        
        # eBay uses different classes for different users. 
        # This list covers the three most common 'title' classes.
        items = soup.select('.s-item__info')
        
        results = []
        for item in items:
            # Attempt to find title in multiple common locations
            title_elem = item.select_one('.s-item__title') or item.select_one('.s-item__title--has-tags')
            
            if not title_elem or "Shop on eBay" in title_elem.text:
                continue
                
            price_elem = item.select_one('.s-item__price')
            link_elem = item.select_one('.s-item__link')
            
            if title_elem and price_elem and link_elem:
                results.append({
                    "target": query,
                    "source": "eBay",
                    "title": title_elem.text.replace("New Listing", "").strip(),
                    "price": price_elem.text.strip(),
                    "url": link_elem['href'].split('?')[0]
                })
        
        return results[:10]
    except Exception as e:
        st.error(f"Scraper encountered an error: {e}")
        return []

def scrape_etsy(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.etsy.com/search?q={query.replace(' ', '%20')}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        listings = soup.select('div.v2-listing-card__info')
        results = []
        for i in listings[:5]:
            title = i.find('h3')
            price = i.find('span', {'class': 'currency-value'})
            link = i.find_parents('a', limit=1)
            if title and price and link:
                results.append({"target": query, "source": "Etsy", "title": title.text.strip(), 
                                 "price": f"${price.text}", "url": link[0]['href'].split('?')[0]})
        return results
    except: return []

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
