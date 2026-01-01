# SCOUT TERMINAL VERSION: 3.16
# UPDATES: Diagnostic Trace, Browser Mimicry, Per-Job Engine Logic

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

# --- 2. THE ENGINE (v3.16 - HIGH RELIABILITY) ---
def run_scout_mission(query, engine_type, custom_domain=None):
    url = "https://serpapi.com/search.json"
    q_str = str(query).strip()
    
    # v3.16 Addition: Mimic a real user browser session
    params = {
        "api_key": SERP_API_KEY,
        "engine": engine_type,
        "device": "desktop",
        "google_domain": "google.com",
        "hl": "en"
    }
    
    if engine_type == "ebay":
        params.update({"_nkw": q_str, "ebay_domain": "ebay.com"})
        res_key = "ebay_results"
    elif engine_type == "custom":
        params.update({"engine": "google", "q": f"site:{custom_domain} {q_str}"})
        res_key = "organic_results"
    else: 
        search_q = f"site:etsy.com {q_str}" if engine_type == "etsy" else q_str
        params.update({"engine": "google_shopping", "q": search_q})
        res_key = "shopping_results"

    try:
        # HUMAN JITTER: 1.5 to 3.5 seconds
        time.sleep(random.uniform(1.5, 3.5)) 
        
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
        
        # DIAGNOSTIC TRACE: Check if the site is actually returning 0 or blocking us
        total_found = data.get("search_information", {}).get("total_results", 0)
        items = data.get(res_key, [])
        
        log_system("trace", f"{engine_type.upper()} Total Found: {total_found} | Displaying: {len(items)}")
        
        processed = []
        if isinstance(items, list):
            for i in items[:15]:
                p_val = i.get("price")
                if isinstance(p_val, dict): p_val = p_val.get("raw", "N/A")
                processed.append({
                    "target": q_str, 
                    "source": engine_type if engine_type != "custom" else custom_domain, 
                    "title": i.get("title", "No Title"), 
                    "price": str(p_val), 
                    "url": i.get("link", "#")
                })
        return processed
    except Exception as e:
        log_system("error", f"CRITICAL FAILURE: {str(e)}")
        return []

# --- 3. UPDATED JOB CREATOR (Logic Fix) ---
with t_conf:
    st.header("⚙️ Automation Jobs")
    with st.expander("📝 Create New Job"):
        with st.form("job_v16"):
            j_name = st.text_input("Job Name:")
            j_targets = st.multiselect("Keywords:", targets_list)
            
            st.write("**Targeted Engines (Ruling out Etsy etc):**")
            c1, c2, c3 = st.columns(3)
            use_ebay = c1.checkbox("eBay", value=True)
            use_etsy = c2.checkbox("Etsy", value=False)
            use_google = c3.checkbox("Google", value=True)
            
            if st.form_submit_button("Save Intelligence Job"):
                # Saving code remains the same as v3.14/15
                st.success(f"Job '{j_name}' locked in.")
                st.rerun()

# --- 4. LOGS (Now with Trace Info) ---
with t_logs:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            # Highlight Trace lines in blue for the user
            for line in lines[-100:]:
                if "[TRACE]" in line:
                    st.info(line)
                else:
                    st.text(line)
