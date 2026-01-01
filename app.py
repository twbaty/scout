import streamlit as st
import pandas as pd
import sqlite3
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

# Custom Dashboard Styling
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
    # Main Intelligence Table
    conn.execute('''CREATE TABLE IF NOT EXISTS items 
                 (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  target TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    # Persistent Search Library Table
    conn.execute('''CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

# --- 3. LIVE EBAY SCRAPER ---
def perform_scout_sweep(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=10"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        listings = soup.find_all('div', {'class': 's-item__info'})
        
        results = []
        for item in listings[1:11]: 
            title = item.find('div', {'class': 's-item__title'})
            price = item.find('span', {'class': 's-item__price'})
            link = item.find('a', {'class': 's-item__link'})
            
            if title and price and link:
                results.append({
                    "target": query,
                    "title": title.text.replace("New Listing", "").strip(),
                    "price": price.text.strip(),
                    "url": link['href'].split('?')[0]
                })
        return results
    except Exception as e:
        st.error(f"Scrape Error for '{query}': {e}")
        return []

# --- 4. SIDEBAR: THE SEARCH LIBRARY ---
init_db()
with st.sidebar:
    st.title("🛡️ Scout Control")
    
    # Add new search terms
    st.subheader("Manage Library")
    new_target = st.text_input("New Target:", placeholder="e.g. Texas Ranger Badge")
    if st.button("➕ Add to Library"):
        if new_target:
            conn = get_db_connection()
            try:
                conn.execute("INSERT INTO targets (name) VALUES (?)", (new_target,))
                conn.commit()
            except sqlite3.IntegrityError:
                st.warning("Already in library.")
            conn.close()
            st.rerun()

    st.divider()
    
    # Checkbox Selection
    st.subheader("Select Targets to Scout")
    conn = get_db_connection()
    all_targets_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
    conn.close()

    selected_targets = []
    for t in all_targets_list:
        if st.checkbox(t, value=True, key=f"check_{t}"):
            selected_targets.append(t)

    st.divider()
    
    run_selected = st.button(f"🚀 Scout {len(selected_targets)} Targets", use_container_width=True)
    
    if st.button("🗑️ Delete Selected from Library"):
        conn = get_db_connection()
        for t in selected_targets:
            conn.execute("DELETE FROM targets WHERE name = ?", (t,))
        conn.commit()
        conn.close()
        st.rerun()

# --- 5. MAIN DASHBOARD ---
st.title("Scout Intelligence Terminal")

# Metrics
conn = get_db_connection()
total_count = pd.read_sql_query("SELECT count(*) as count FROM items", conn).iloc[0]['count']
new_today = pd.read_sql_query("SELECT count(*) as count FROM items WHERE found_date > datetime('now', '-1 day')", conn).iloc[0]['count']
conn.close()

m_col1, m_col2, m_col3 = st.columns(3)
m_col1.metric("90-Day Archive", total_count)
m_col2.metric("New Finds (Today)", new_today)
m_col3.metric("System Status", "Live/Operational")

tab1, tab2 = st.tabs(["📊 Live Intelligence", "📜 90-Day Archive"])

with tab1:
    if run_selected:
        if not selected_targets:
            st.warning("Please check at least one target in the sidebar.")
        else:
            all_found_items = []
            with st.status(f"Scanning {len(selected_targets)} targets...", expanded=True) as status:
                for target in selected_targets:
                    st.write(f"Scouting eBay for: **{target}**")
                    found = perform_scout_sweep(target)
                    
                    conn = get_db_connection()
                    for item in found:
                        all_found_items.append(item)
                        try:
                            conn.execute("INSERT INTO items (target, title, price, url) VALUES (?, ?, ?, ?)",
                                         (item['target'], item['title'], item['price'], item['url']))
                        except sqlite3.IntegrityError:
                            pass 
                    conn.commit()
                    conn.close()
                status.update(label="✅ Selective Sweep Complete!", state="complete")
            
            # Show live results immediately
            st.subheader(f"Current Results ({len(all_found_items)} items found)")
            if all_found_items:
                live_df = pd.DataFrame(all_found_items)
                st.dataframe(
                    live_df,
                    column_config={"url": st.column_config.LinkColumn("View Listing")},
                    use_container_width=True, 
                    hide_index=True
                )
                if st.button("🔄 Update Global Stats"):
                    st.rerun()
            else:
                st.info("No listings found for the selected targets.")
    else:
        st.info("Select targets in the sidebar and click 'Scout' to begin.")

with tab2:
    st.subheader("Historical Intelligence (Last 90 Days)")
    conn = get_db_connection()
    history_df = pd.read_sql_query("SELECT found_date as Date, target as Target, title as Item, price as Cost, url as Link FROM items ORDER BY found_date DESC", conn)
    conn.close()

    if not history_df.empty:
        st.dataframe(
            history_df,
            column_config={
                "Link": st.column_config.LinkColumn("View Listing"),
                "Date": st.column_config.DatetimeColumn("Detected", format="D MMM, YY - h:mm A")
            },
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.write("Archive is currently empty.")
