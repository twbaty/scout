# SCOUT TERMINAL VERSION: 3.23
# UPDATES: 2026 Syntax Compliance, Global Tab Scope, Zero-Result Diagnostic Trace

import streamlit as st
import pandas as pd
import sqlite3
import requests
import os
import time
import random
import logging

# --- 1. CORE SYSTEM SETUP ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

# --- 2. LOGGING & DATABASE ---
LOG_FILE = 'scout.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db_connection():
    return sqlite3.connect("scout.db", check_same_thread=False)

# --- 3. UI TAB INITIALIZATION (Defined globally to prevent NameError) ---
t_live, t_arch, t_conf, t_logs = st.tabs(["📡 Live Results", "📜 Archive", "⚙️ Jobs & Config", "🛠️ Logs"])

# --- 4. THE ENGINE (Reinforced for ENIAC & CRAY) ---
def run_scout_mission(query, engine_type, custom_domain=None):
    url = "https://serpapi.com/search.json"
    q_str = str(query).strip()
    # Safely pull API Key
    try:
        api_key = st.secrets["SERPAPI_KEY"]
    except:
        st.error("Missing SERPAPI_KEY in secrets.")
        return []

    params = {"api_key": api_key, "engine": engine_type, "device": "desktop", "hl": "en"}
    
    if engine_type == "ebay":
        params.update({"_nkw": q_str, "ebay_domain": "ebay.com"})
        res_keys = ["ebay_results", "listings", "shopping_results"]
    elif engine_type == "custom":
        params.update({"engine": "google", "q": f"site:{custom_domain} {q_str}"})
        res_keys = ["organic_results"]
    else: 
        search_q = f"site:etsy.com {q_str}" if engine_type == "etsy" else q_str
        params.update({"engine": "google_shopping", "q": search_q})
        res_keys = ["shopping_results", "organic_results"]

    try:
        time.sleep(random.uniform(1.2, 2.8)) 
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
        
        # Agnostic Deep-Parsing
        items = []
        for key in res_keys:
            if key in data and isinstance(data[key], list):
                items = data[key]
                break
        
        # Record search meta-info for debugging
        total_found = data.get("search_information", {}).get("total_results", 0)
        log_event("RESPONSE", f"SUCCESS: {engine_type.upper()} found {len(items)} (Total Ref: {total_found}) for {q_str}")
        
        processed = []
        for i in items[:15]:
            link = i.get("link", i.get("product_link", "#"))
            price = i.get("price")
            if isinstance(price, dict): price = price.get("raw", "N/A")
            processed.append({
                "target": q_str, "source": engine_type if engine_type != "custom" else custom_domain, 
                "title": i.get("title", "No Title"), "price": str(price or "N/A"), "url": link
            })
        return processed
    except Exception as e:
        log_event("ERROR", f"Mission Failure: {str(e)}")
        return []

# --- 5. SIDEBAR (2026 Compliant) ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.23")
    # Updated to 'stretch' per 2026 requirements
    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state['run_sweep'] = True
    
    # ... [Library and Toggle code] ...

# --- 6. LOGS (Hardened) ---
with t_logs:
    st.subheader("🛠️ System Logs")
    if st.button("🗑️ Purge Log", width="stretch"):
        open(LOG_FILE, 'w').close()
        st.rerun()
    
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-100:]))
