# SCOUT TERMINAL VERSION: 3.48
# PURPOSE: First working execution pipeline (ad-hoc search inserts results)

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import logging
from datetime import datetime

# --- [1. SYSTEM CORE] ---
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

LOG_FILE = "scout.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log_event(tag, msg):
    logging.info(f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# --- [2. COLLECTOR (PROOF OF LIFE)] ---
def fake_search(targets, sites):
    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for site in sites:
        for t in targets:
            rows.append((
                now,
                t,
                site,
                f"{t} vintage item on {site}",
                "$199.99",
                f"https://{site}/item/{t}"
            ))
    return rows

# --- [3. SIDEBAR] ---
with st.sidebar:
    st.title("🛡️ SCOUT v3.48")

    conn = get_db()

    st.subheader("📡 Deep Search Sites")
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)["domain"].tolist()
    active_sites = [s for s in c_list if st.toggle(s, value=True, key=f"site_{s}")]

    st.divider()

    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("add_keyword", clear_on_submit=True):
            nk = st.text_input("New Target")
            if st.form_submit_button("＋"):
                if nk:
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nk,))
                    conn.commit()
                    log_event("BUTTON", f"Added target '{nk}'")
                    st.rerun()

        t_list = pd.read_sql_query("SELECT name FROM targets", conn)["name"].tolist()
        selected_targets = []

        for t in t_list:
            c1, c2 = st.columns([4, 1])
            if c1.checkbox(t, value=True, key=f"sel_{t}"):
                selected_targets.append(t)
            if c2.button("🗑️", key=f"del_{t}"):
                conn.execute("DELETE FROM targets WHERE name=?", (t,))
                conn.commit()
                log_event("BUTTON", f"Deleted target '{t}'")
                st.rerun()

    st.markdown("<br>" * 4, unsafe_allow_html=True)

    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state["run_sweep"] = True
        log_event("BUTTON", "Manual sweep initiated")

    conn.close()

# --- [4. MAIN UI] ---
t_live, t_arch, t_jobs, t_logs = st.tabs(
    ["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"]
)

# --- LIVE FEED ---
with t_live:
    c_main, c_stat = st.columns([3, 1])

    with c_main:
        if st.session_state.get("run_sweep"):
            with st.status("📡 Sweeping…") as status:
                conn = get_db()

                rows = fake_search(selected_targets, active_sites)

                if rows:
                    conn.executemany(
                        """
                        INSERT INTO items
                        (found_date, target, source, title, price, url)
                        VALUES (?,?,?,?,?,?)
                        """,
                        rows
                    )
                    conn.commit()
                    log_event("ENGINE", f"Inserted {len(rows)} items")

                results = pd.read_sql_query(
                    "SELECT found_date, target, source, title, price, url FROM items ORDER BY found_date DESC",
                    conn
                )

                conn.close()
                status.update(label=f"Sweep complete: {len(results)} total items", state="complete")

            st.dataframe(results, use_container_width=True, hide_index=True)
            st.session_state["run_sweep"] = False
        else:
            st.info("Terminal ready.")

    with c_stat:
        st.subheader("📡 Status")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                st.code(lines[-1] if lines else "Ready")

# --- ARCHIVE ---
with t_arch:
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC", conn)
    conn.close()
    st.dataframe(df, use_container_width=True, hide_index=True)

# --- JOBS & CONFIG ---
with t_jobs:
    st.header("⚙️ Jobs & Config")

    st.subheader("📡 Register New Site")
    with st.form("add_site", clear_on_submit=True):
        ns = st.text_input("Domain (e.g. ebay.com)")
        if st.form_submit_button("Add"):
            if ns:
                conn = get_db()
                conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (ns,))
                conn.commit()
                conn.close()
                log_event("BUTTON", f"Added site '{ns}'")
                st.rerun()

# --- LOGS ---
with t_logs:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-100:]))
