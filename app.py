import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

# Custom Styling for a Professional Application Look
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 2rem; color: #58a6ff; }
    .stDataFrame { border: 1px solid #30363d; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE ENGINE ---
def get_db_connection():
    conn = sqlite3.connect("scout.db", check_same_thread=False)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS items 
                 (id INTEGER PRIMARY KEY, 
                  found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  target TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    conn.commit()
    conn.close()

# --- 3. THE "BRAIN" (MOCK SCRAPER) ---
def perform_scout_sweep(query):
    """Simulates the eBay search logic with progress feedback."""
    # This is where the BeautifulSoup logic lives in the CLI version
    time.sleep(1.5) # Simulating network lag
    mock_results = [
        {"target": query, "title": f"{query} - Vintage Collection", "price": "$145.00", "url": "https://ebay.com"},
        {"target": query, "title": f"Rare {query} (Authentic)", "price": "$310.00", "url": "https://ebay.com"}
    ]
    return mock_results

# --- 4. SIDEBAR CONTROLS ---
with st.sidebar:
    st.image("https://img.icons8.com/officel/80/shield.png", width=60)
    st.title("Scout Control")
    st.divider()
    
    search_query = st.text_input("Manual Intelligence Sweep:", placeholder="e.g. Texas Ranger Badge")
    run_button = st.button("🚀 Execute Search", use_container_width=True)
    
    st.divider()
    if st.button("🛠️ Reset Local Database"):
        conn = get_db_connection()
        conn.execute("DROP TABLE IF EXISTS items")
        init_db()
        st.warning("Database cleared.")

# --- 5. MAIN DASHBOARD UI ---
st.title("🛡️ Scout Intelligence Terminal")
init_db() # Ensure DB is ready on every load

# Top Level Metrics
conn = get_db_connection()
total_count = pd.read_sql_query("SELECT count(*) as count FROM items", conn).iloc[0]['count']
new_today = pd.read_sql_query("SELECT count(*) as count FROM items WHERE found_date > datetime('now', '-1 day')", conn).iloc[0]['count']
conn.close()

m_col1, m_col2, m_col3 = st.columns(3)
m_col1.metric("90-Day Archive", total_count)
m_col2.metric("New Finds (24h)", new_today, delta=f"+{new_today} items")
m_col3.metric("System Status", "Operational", delta_color="normal")

# Tabs for Organization
tab1, tab2 = st.tabs(["📊 Live Intelligence", "📜 Intelligence Archive"])

with tab1:
    if run_button and search_query:
        with st.status(f"🔍 Scouting eBay for '{search_query}'...", expanded=True) as status:
            st.write("Initializing secure connection...")
            time.sleep(1)
            
            st.write("Parsing listings and verifying authenticity...")
            results = perform_scout_sweep(search_query)
            
            st.write("Updating local intelligence database...")
            conn = get_db_connection()
            for item in results:
                try:
                    conn.execute("INSERT INTO items (target, title, price, url) VALUES (?, ?, ?, ?)",
                                 (item['target'], item['title'], item['price'], item['url']))
                except sqlite3.IntegrityError:
                    pass # Duplicate skip
            conn.commit()
            conn.close()
            
            status.update(label="✅ Sweep Complete!", state="complete", expanded=False)
        
        st.success(f"Found {len(results)} matches for {search_query}.")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
    
    elif run_button and not search_query:
        st.warning("Please enter a search term in the sidebar.")
    else:
        st.info("The terminal is idle. Initiate a sweep from the sidebar to begin.")

with tab2:
    st.subheader("Rolling 90-Day Intelligence History")
    conn = get_db_connection()
    history_df = pd.read_sql_query("SELECT found_date as Date, target as Target, title as Item, price as Cost, url as Link FROM items ORDER BY found_date DESC", conn)
    conn.close()

    if not history_df.empty:
        st.dataframe(
            history_df,
            column_config={
                "Link": st.column_config.LinkColumn("View on eBay"),
                "Date": st.column_config.DatetimeColumn("Date Found", format="D MMM, YYYY")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.write("No historical data available. Run your first scout to populate the archive.")
