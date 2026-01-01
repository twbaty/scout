import streamlit as st
import pandas as pd
import sqlite3
import requests
import os
from datetime import datetime

# --- 1. CORE SYSTEM CONFIG ---
st.set_page_config(page_title="SCOUT | Production Terminal", layout="wide")

# Secure API Key Check
if "SERPAPI_KEY" in st.secrets:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
else:
    st.error("🔑 Missing SerpApi Key! Please add it to your secrets.toml file.")
    st.stop()

# --- 2. DATABASE ARCHITECTURE ---
def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    # Unique URL constraint prevents duplicate items from cluttering the archive
    conn.execute('''CREATE TABLE IF NOT EXISTS items 
                   (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                    target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY, last_run TIMESTAMP)')
    
    # FORCED NORMALIZATION: Fixes old "ebay/Ebay/eBay" mess on every startup
    conn.execute("UPDATE items SET source = 'Ebay' WHERE LOWER(source) = 'ebay'")
    conn.execute("UPDATE items SET source = 'Etsy' WHERE LOWER(source) = 'etsy'")
    conn.execute("UPDATE items SET source = 'Google Shopping' WHERE LOWER(source) LIKE 'google%'")
    conn.commit()
    conn.close()

init_db()

# --- 3. THE UNIVERSAL ENGINE TRANSLATOR ---
def run_scout_mission(query, engine_type):
    """Handles the unique API requirements for different marketplaces."""
    url = "https://serpapi.com/search.json"
    q = str(query).strip()
    
    # Default parameters
    params = {"api_key": SERP_API_KEY}
    source_label = engine_type.title()
    results_key = "shopping_results"

    if engine_type == "ebay":
        params.update({"engine": "ebay", "_nkw": q})
        source_label = "Ebay"
        results_key = "ebay_results"
    elif engine_type == "etsy":
        # THE TRICK: Google Shopping engine + site filter
        params.update({"engine": "google_shopping", "q": f"site:etsy.com {q}"})
        source_label = "Etsy"
    elif engine_type == "amazon":
        params.update({"engine": "amazon", "q": q})
        source_label = "Amazon"
        # Amazon results can appear in shopping_results or organic_results
    else:
        params.update({"engine": "google_shopping", "q": q})
        source_label = "Google Shopping"

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        # Determine where the items are located in the JSON response
        if engine_type == "amazon" and "shopping_results" not in data:
            results_key = "organic_results"
        
        items = data.get(results_key, [])
        processed = []
        
        if isinstance(items, list):
            for i in items[:15]: # Capture top 15 results
                price = i.get("price")
                price_val = price.get("raw", "N/A") if isinstance(price, dict) else str(price or "N/A")
                
                processed.append({
                    "target": q,
                    "source": source_label,
                    "title": i.get("title", "No Title"),
                    "price": price_val,
                    "url": i.get("link", i.get("product_link", "#"))
                })
        return processed
    except Exception as e:
        return []

# --- 4. PRODUCTION INTERFACE ---
st.title("🛡️ SCOUT | Intelligence Terminal")

with st.sidebar:
    st.header("📡 Mission Control")
    engines = {
        "ebay": st.toggle("Ebay", value=True),
        "etsy": st.toggle("Etsy", value=True),
        "google": st.toggle("Google Shopping", value=True),
        "amazon": st.toggle("Amazon", value=False)
    }
    
    st.divider()
    target_q = st.text_input("🎯 Active Target:", value="sewing kit")
    execute_btn = st.button("🚀 EXECUTE SWEEP", type="primary", use_container_width=True)

# --- 5. DATA TABS ---
t_live, t_dash, t_arch = st.tabs(["📡 Live Intel", "📊 Market Dashboard", "📜 Archive"])

with t_live:
    if execute_btn:
        all_found = []
        with st.status(f"Scanning marketplaces for '{target_q}'...", expanded=True) as status:
            for eng, active in engines.items():
                if active:
                    st.write(f"Querying {eng.title()}...")
                    results = run_scout_mission(target_q, eng)
                    all_found.extend(results)
            
            # Save results to DB (Ignore duplicates automatically via UNIQUE url constraint)
            conn = get_db_connection()
            for item in all_found:
                try:
                    conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?, ?, ?, ?, ?)",
                                 (item['target'], item['source'], item['title'], item['price'], item['url']))
                except: pass 
            conn.commit()
            conn.close()
            
            st.session_state['current_intel'] = all_found
            status.update(label="✅ Sweep Complete", state="complete")

    if 'current_intel' in st.session_state:
        # DATA DISPLAY WITH CLICKABLE LINKS
        st.dataframe(
            pd.DataFrame(st.session_state['current_intel']),
            column_config={
                "url": st.column_config.LinkColumn("Product Link", display_text="View Item"),
                "source": st.column_config.TextColumn("Marketplace")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Terminal ready. Configure Mission Control and Execute.")

with t_dash:
    conn = get_db_connection()
    db_df = pd.read_sql_query("SELECT source, target FROM items", conn)
    conn.close()
    
    if not db_df.empty:
        st.subheader("Distribution of Found Items")
        pivot = db_df.groupby(['target', 'source']).size().unstack(fill_value=0)
        st.table(pivot) # Clean, non-interactive table for scannability
    else:
        st.write("No data available in archive yet.")

with t_arch:
    conn = get_db_connection()
    arch_df = pd.read_sql_query("SELECT found_date, source, target, title, price, url FROM items ORDER BY found_date DESC LIMIT 100", conn)
    conn.close()
    
    st.dataframe(
        arch_df,
        column_config={"url": st.column_config.LinkColumn("Link", display_text="Open")},
        use_container_width=True,
        hide_index=True
    )
