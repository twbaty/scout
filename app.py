import streamlit as st
import pandas as pd
import sqlite3
import requests
import os
from datetime import datetime

# --- 1. CORE SYSTEM CONFIG ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

if "SERPAPI_KEY" in st.secrets:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
else:
    st.error("🔑 Missing SerpApi Key in secrets.toml")
    st.stop()

# --- 2. DATABASE & RESTORATION ---
def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    # Ensure all tables exist
    conn.execute('''CREATE TABLE IF NOT EXISTS items 
                   (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                    target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS targets 
                   (name TEXT PRIMARY KEY, frequency TEXT DEFAULT 'Manual', last_run TIMESTAMP)''')
    
    # FORCED NORMALIZATION: Clean up the eBay/ebay/Etsy mess on every launch
    conn.execute("UPDATE items SET source = 'Ebay' WHERE LOWER(source) = 'ebay'")
    conn.execute("UPDATE items SET source = 'Etsy' WHERE LOWER(source) = 'etsy'")
    conn.execute("UPDATE items SET source = 'Google Shopping' WHERE LOWER(source) LIKE 'google%'")
    conn.commit()
    conn.close()

init_db()

# --- 3. THE REFINED ENGINE LOGIC (Etsy & eBay Fixes) ---
def run_scout_mission(query, engine_type):
    url = "https://serpapi.com/search.json"
    q = str(query).strip()
    params = {"api_key": SERP_API_KEY}
    source_label = engine_type.title()
    res_key = "shopping_results"

    if engine_type == "ebay":
        params.update({"engine": "ebay", "_nkw": q})
        source_label = "Ebay"
        res_key = "ebay_results"
    elif engine_type == "etsy":
        params.update({"engine": "google_shopping", "q": f"site:etsy.com {q}"})
        source_label = "Etsy"
    elif engine_type == "amazon":
        params.update({"engine": "amazon", "q": q})
        source_label = "Amazon"
    else:
        params.update({"engine": "google_shopping", "q": q})
        source_label = "Google Shopping"

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        if engine_type == "amazon" and "shopping_results" not in data: res_key = "organic_results"
        
        items = data.get(res_key, [])
        processed = []
        if isinstance(items, list):
            for i in items[:15]:
                p = i.get("price")
                price_val = p.get("raw", "N/A") if isinstance(p, dict) else str(p or "N/A")
                processed.append({
                    "target": q, "source": source_label, "title": i.get("title", "No Title"),
                    "price": price_val, "url": i.get("link", i.get("product_link", "#"))
                })
        return processed
    except:
        return []

# --- 4. SIDEBAR (LIBRARY MANAGEMENT) ---
with st.sidebar:
    st.title("🛡️ SCOUT")
    
    with st.expander("➕ Register New Target", expanded=False):
        new_k = st.text_input("Keyword:")
        if st.button("Add to Library", use_container_width=True) and new_k:
            conn = get_db_connection()
            conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_k,))
            conn.commit(); conn.close()
            st.rerun()

    st.divider()
    st.subheader("Target Library")
    conn = get_db_connection()
    targets_df = pd.read_sql_query("SELECT name FROM targets", conn)
    conn.close()
    
    selected_targets = []
    for t in targets_df['name']:
        c1, c2 = st.columns([4, 1])
        if c1.checkbox(t, value=True, key=f"cb_{t}"):
            selected_targets.append(t)
        if c2.button("🗑️", key=f"del_{t}"):
            conn = get_db_connection()
            conn.execute("DELETE FROM targets WHERE name = ?", (t,))
            conn.commit(); conn.close()
            st.rerun()
    
    st.divider()
    execute_btn = st.button("🚀 EXECUTE SWEEP", type="primary", use_container_width=True)

# --- 5. TABS (CONFIG & SCHEDULING RESTORED) ---
t_live, t_dash, t_arch, t_conf = st.tabs(["📡 Live Intel", "📊 Dashboard", "📜 Archive", "⚙️ Config"])

with t_live:
    if execute_btn and selected_targets:
        all_found = []
        with st.status("Scanning Marketplaces...", expanded=True) as status:
            for target in selected_targets:
                st.write(f"Scouting: **{target}**")
                if st.session_state.get('p_ebay', True): all_found.extend(run_scout_mission(target, "ebay"))
                if st.session_state.get('p_etsy', True): all_found.extend(run_scout_mission(target, "etsy"))
                if st.session_state.get('p_google', True): all_found.extend(run_scout_mission(target, "google_shopping"))
                if st.session_state.get('p_amazon', False): all_found.extend(run_scout_mission(target, "amazon"))
            
            conn = get_db_connection()
            for h in all_found:
                try: conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?, ?, ?, ?, ?)", (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass
            conn.commit(); conn.close()
            st.session_state['last_results'] = all_found
            status.update(label="✅ Sweep Complete", state="complete")

    if 'last_results' in st.session_state:
        st.dataframe(pd.DataFrame(st.session_state['last_results']), 
                     column_config={"url": st.column_config.LinkColumn("Link", display_text="View Item")},
                     use_container_width=True, hide_index=True)

with t_dash:
    conn = get_db_connection()
    db_df = pd.read_sql_query("SELECT source, target FROM items", conn)
    conn.close()
    if not db_df.empty:
        pivot = db_df.groupby(['target', 'source']).size().unstack(fill_value=0)
        st.table(pivot)

with t_arch:
    conn = get_db_connection()
    arch_df = pd.read_sql_query("SELECT found_date, source, target, title, price, url FROM items ORDER BY found_date DESC LIMIT 100", conn)
    conn.close()
    st.dataframe(arch_df, column_config={"url": st.column_config.LinkColumn("Link")}, use_container_width=True, hide_index=True)

with t_conf:
    st.header("⚙️ System Configuration")
    st.subheader("1. Active Engines")
    c1, c2, c3, c4 = st.columns(4)
    c1.toggle("eBay", value=True, key="p_ebay")
    c2.toggle("Etsy", value=True, key="p_etsy")
    c3.toggle("Google Shopping", value=True, key="p_google")
    c4.toggle("Amazon", value=False, key="p_amazon")
    
    st.divider()
    st.subheader("2. Target Scheduling")
    conn = get_db_connection()
    sched_df = pd.read_sql_query("SELECT * FROM targets", conn)
    conn.close()
    
    opts = ["Manual", "Daily", "Weekly"]
    for _, row in sched_df.iterrows():
        r1, r2, r3 = st.columns([3, 2, 1])
        r1.write(f"**{row['name']}**")
        curr = row['frequency'] if row['frequency'] in opts else "Manual"
        new_f = r2.selectbox("Freq", opts, index=opts.index(curr), key=f"f_{row['name']}")
        if new_f != row['frequency']:
            conn = get_db_connection()
            conn.execute("UPDATE targets SET frequency = ? WHERE name = ?", (new_f, row['name']))
            conn.commit(); conn.close()
            st.rerun()
        r3.write(f"Last: {row['last_run']}")
