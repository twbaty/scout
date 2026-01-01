import streamlit as st
import pandas as pd
import sqlite3
import requests
import os
import logging
from datetime import datetime

# --- 1. CORE SYSTEM SETUP ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

if "SERPAPI_KEY" in st.secrets:
    SERP_API_KEY = st.secrets["SERPAPI_KEY"]
else:
    st.error("🔑 Missing SerpApi Key")
    st.stop()

# --- 2. LOGGING & DB ---
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, target TEXT, source TEXT, title TEXT, price TEXT, url TEXT UNIQUE)')
    conn.execute('CREATE TABLE IF NOT EXISTS targets (name TEXT PRIMARY KEY, frequency TEXT DEFAULT "Manual", last_run TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS custom_sites (domain TEXT PRIMARY KEY)')
    conn.commit(); conn.close()

init_db()

# --- 3. THE UNIVERSAL ENGINE ---
def run_scout_mission(query, engine_type, custom_domain=None):
    url = "https://serpapi.com/search.json"
    q = str(query).strip()
    params = {"api_key": SERP_API_KEY}
    
    if engine_type == "ebay":
        params.update({"engine": "ebay", "_nkw": q})
        res_key, label = "ebay_results", "Ebay"
    elif engine_type == "custom":
        params.update({"engine": "google", "q": f"site:{custom_domain} {q}"})
        res_key, label = "organic_results", custom_domain.split('.')[0].title()
    else: 
        search_q = f"site:etsy.com {q}" if engine_type == "etsy" else q
        params.update({"engine": "google_shopping", "q": search_q})
        res_key, label = "shopping_results", engine_type.title()

    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        items = data.get(res_key, [])
        logging.info(f"Sweep: {label} | Target: {q} | Hits: {len(items) if items else 0}")
        
        processed = []
        if isinstance(items, list):
            for i in items[:15]:
                p = i.get("price")
                p_val = p.get("raw", "N/A") if isinstance(p, dict) else str(p or "N/A")
                processed.append({
                    "target": q, "source": label, "title": i.get("title", i.get("name", "No Title")),
                    "price": p_val, "url": i.get("link", "#")
                })
        return processed
    except Exception as e:
        logging.error(f"Error on {label}: {str(e)}")
        return []

# --- 4. SIDEBAR LIBRARY ---
with st.sidebar:
    st.title("🛡️ SCOUT")
    
    # Keyword Registration
    with st.expander("➕ Register Target", expanded=False):
        with st.form("target_form", clear_on_submit=True):
            new_k = st.text_input("Keyword:")
            if st.form_submit_button("Add to Library"):
                if new_k:
                    conn = get_db_connection()
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (new_k,))
                    conn.commit(); conn.close()
                    st.rerun()

    st.divider()
    conn = get_db_connection()
    targets_list = pd.read_sql_query("SELECT name FROM targets", conn)['name'].tolist()
    conn.close()
    
    selected_targets = []
    for t in targets_list:
        c1, c2 = st.columns([4, 1])
        if c1.checkbox(t, value=True, key=f"cb_{t}"): selected_targets.append(t)
        if c2.button("🗑️", key=f"del_{t}"):
            conn = get_db_connection()
            conn.execute("DELETE FROM targets WHERE name = ?", (t,))
            conn.commit(); conn.close()
            st.rerun()
    
    st.divider()
    execute_sweep = st.button("🚀 EXECUTE SWEEP", type="primary", use_container_width=True)

# --- 5. TABS ---
t_live, t_dash, t_arch, t_conf, t_logs = st.tabs(["📡 Live Results", "📊 Dashboard", "📜 Archive", "⚙️ Config", "🛠️ Logs"])

with t_live:
    if execute_sweep and selected_targets:
        hits = []
        with st.status("Gathering Intel...") as status:
            conn = get_db_connection()
            customs = pd.read_sql_query("SELECT domain FROM custom_sites", conn)['domain'].tolist()
            conn.close()

            for target in selected_targets:
                if st.session_state.get('p_ebay', True): hits.extend(run_scout_mission(target, "ebay"))
                if st.session_state.get('p_etsy', True): hits.extend(run_scout_mission(target, "etsy"))
                if st.session_state.get('p_google', True): hits.extend(run_scout_mission(target, "google"))
                for site in customs:
                    hits.extend(run_scout_mission(target, "custom", site))
            
            conn = get_db_connection()
            for h in hits:
                try: conn.execute("INSERT INTO items (target, source, title, price, url) VALUES (?,?,?,?,?)", (h['target'], h['source'], h['title'], h['price'], h['url']))
                except: pass
            conn.commit(); conn.close()
            st.session_state['last_run'] = hits
            status.update(label="Sweep Complete", state="complete")

    if 'last_run' in st.session_state:
        st.dataframe(pd.DataFrame(st.session_state['last_run']), 
                     column_config={"url": st.column_config.LinkColumn("Link", display_text="Open")},
                     use_container_width=True, hide_index=True)

with t_dash:
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT source, target FROM items", conn)
    conn.close()
    if not df.empty:
        st.table(df.groupby(['target', 'source']).size().unstack(fill_value=0))

with t_arch:
    conn = get_db_connection()
    df_arch = pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC LIMIT 100", conn)
    conn.close()
    st.dataframe(df_arch, column_config={"url": st.column_config.LinkColumn("Link")}, use_container_width=True, hide_index=True)

with t_conf:
    st.subheader("1. Marketplace Toggles")
    c1, c2, c3 = st.columns(3)
    c1.toggle("Ebay", value=True, key="p_ebay")
    c2.toggle("Etsy", value=True, key="p_etsy")
    c3.toggle("Google Shopping", value=True, key="p_google")
    
    st.divider()
    st.subheader("2. Target Scheduling")
    conn = get_db_connection()
    s_df = pd.read_sql_query("SELECT * FROM targets", conn)
    conn.close()
    
    sched_opts = ["Manual", "Daily", "M-W-F", "Weekly", "Bi-Weekly"]
    for _, r in s_df.iterrows():
        sc1, sc2 = st.columns([3, 2])
        sc1.write(r['name'])
        curr = r['frequency'] if r['frequency'] in sched_opts else "Manual"
        new_f = sc2.selectbox("Schedule", sched_opts, index=sched_opts.index(curr), key=f"f_{r['name']}")
        if new_f != r['frequency']:
            conn = get_db_connection()
            conn.execute("UPDATE targets SET frequency = ? WHERE name = ?", (new_f, r['name']))
            conn.commit(); conn.close(); st.rerun()

    st.divider()
    st.subheader("3. Custom Domain Registration")
    
    # FORM WRAPPER: Ensures domain registration is captured reliably
    with st.form("custom_site_form", clear_on_submit=True):
        new_site = st.text_input("Domain (e.g. vintage-computer.com):")
        submitted = st.form_submit_button("Register Custom Site")
        if submitted and new_site:
            conn = get_db_connection()
            conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (new_site,))
            conn.commit(); conn.close()
            st.toast(f"Registered {new_site}!")
            st.rerun()

    st.write("#### Currently Registered Sites")
    conn = get_db_connection()
    sites_df = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
    conn.close()
    for s in sites_df['domain']:
        c_site, c_del = st.columns([5, 1])
        c_site.code(s)
        if c_del.button("🗑️", key=f"del_site_{s}"):
            conn = get_db_connection()
            conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
            conn.commit(); conn.close()
            st.rerun()

with t_logs:
    if st.button("Clear Logs"):
        open(LOG_FILE, 'w').close()
        st.rerun()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            st.code("".join(f.readlines()[-50:]))
