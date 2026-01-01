# SCOUT TERMINAL VERSION: 3.19
# UPDATES: Agnostic eBay Parsing, Sidebar Stats, Error-Resilient Mapping

import streamlit as st
import pandas as pd
import sqlite3
import requests
import os
import time
import random
import logging

# ... [Core Setup & DB Logic remain identical to v3.18] ...

# --- 3. REINFORCED ENGINE (v3.19 - AGNOSTIC PARSING) ---
def run_scout_mission(query, engine_type, custom_domain=None):
    url = "https://serpapi.com/search.json"
    q_str = str(query).strip()
    params = {"api_key": SERP_API_KEY, "engine": engine_type, "device": "desktop"}
    
    if engine_type == "ebay":
        params.update({"_nkw": q_str})
        res_keys = ["ebay_results", "listings", "ads"] # Try multiple keys
    elif engine_type == "custom":
        params.update({"engine": "google", "q": f"site:{custom_domain} {q_str}"})
        res_keys = ["organic_results"]
    else: 
        search_q = f"site:etsy.com {q_str}" if engine_type == "etsy" else q_str
        params.update({"engine": "google_shopping", "q": search_q})
        res_keys = ["shopping_results", "organic_results"]

    try:
        time.sleep(random.uniform(1.0, 2.0)) 
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
        
        # TRACE LOGGING
        total = data.get("search_information", {}).get("total_results", 0)
        
        # AGNOSTIC PARSING: Check all potential result keys
        items = []
        for key in res_keys:
            if key in data and isinstance(data[key], list):
                items = data[key]
                break
        
        log_system("trace", f"{engine_type.upper()} '{q_str}': Total {total} | Parsed {len(items)}")
        
        processed = []
        for i in items[:15]:
            # Robust Link/Price Extraction
            link = i.get("link", i.get("product_link", i.get("url", "#")))
            price = i.get("price")
            if isinstance(price, dict): price = price.get("raw", "N/A")
            
            processed.append({
                "target": q_str, 
                "source": engine_type if engine_type != "custom" else custom_domain, 
                "title": i.get("title", "No Title"), 
                "price": str(price or "N/A"), 
                "url": link
            })
        return processed
    except Exception as e:
        log_system("error", f"Parsing Error: {str(e)}")
        return []

# --- 5. SIDEBAR (WITH QUICK STATS) ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.19")
    # ... [Toggles & Library logic] ...
    
    st.divider()
    if 'last_trace' in st.session_state:
        st.subheader("📊 Last Sweep Intel")
        st.caption(st.session_state['last_trace'])

# --- 6. TABS ---
# ... [Live Results & Logs logic] ...
