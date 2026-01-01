# ============================================================
# SCOUT – Intelligence Terminal
# VERSION: 3.62
#
# STATUS:
# - Google Search via SerpAPI: ENABLED
# - eBay Marketplace (SerpAPI): PLANNED (disabled in UI)
# - Amazon Marketplace (SerpAPI): PLANNED (disabled in UI)
# - Etsy Marketplace (SerpAPI): PLANNED (disabled in UI)
#
# NOTES:
# - Site-based searches are performed via Google dorking:
#   site:<domain> <keyword>
# - API key loaded from .streamlit/secrets.toml
# - UI is intentionally explicit about active vs planned engines
# ============================================================

import streamlit as st
import pandas as pd
import sqlite3
import os
import logging
import requests
from datetime import datetime

# ---------------- SYSTEM CORE ----------------
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

LOG_FILE = "scout.log"
SERPAPI_KEY = st.secrets.get("SERPAPI_KEY")

if not SERPAPI_KEY:
    st.error("SERPAPI_KEY not found in .streamlit/secrets.toml")
    st.stop()

if "log_level" not in st.session_state:
    st.session_state["log_level"] = logging.INFO

logging.basicConfig(
    filename=LOG_FILE,
    level=st.session_state["log_level"],
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log_event(tag, msg, level=logging.INFO):
    logging.log(level, f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# ---------------- COLLECTOR ----------------
def google_serpapi_dork(keyword, domain):
    query = f"site:{domain} {keyword}"
    log_event("COLLECTOR", f"Google dork: {query}")

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": 10
    }

    r = requests.get("https://serpapi.com/search", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for res in data.get("organic_results", []):
        rows.append((
            now,
            keyword,
            domain,
            res.get("title"),
            None,
            res.get("link")
        ))

    log_event("COLLECTOR", f"{len(rows)} results for {query}")
    return rows

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.title("🛡️ SCOUT v3.62")

    st.subheader("🔍 Search Engines (SerpAPI)")
    st.checkbox("Google (site-based)", value=True, disabled=True)
    st.checkbox("eBay (Marketplace)", value=False, disabled=True, help="Planned")
    st.checkbox("Amazon (Marketplace)", value=False, disabled=True, help="Planned")
    st.checkbox("Etsy (Marketplace)", value=False, disabled=True, help="Planned")

    st.caption("Active engine: Google Search via SerpAPI")
    st.divider()

    conn = get_db()
    st.subheader("📡 Sites (searched via Google)")
    sites = pd.read_sql_query("SELECT domain FROM custom_sites", conn)["domain"].tolist()
    active_sites = [s for s in sites if st.toggle(s, value=True, key=f"site_{s}")]

    st.divider()

    with st.expander("🎯 Keywords", expanded=True):
        with st.form("add_keyword", clear_on_submit=True):
            nk = st.text_input("New Keyword")
            if st.form_submit_button("＋") and nk:
                conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nk,))
                conn.commit()
                log_event("CONFIG", f"Added keyword '{nk}'")
                st.rerun()

        t_list = pd.read_sql_query("SELECT name FROM targets", conn)["name"].tolist()
        selected_targets = [t for t in t_list if st.checkbox(t, value=True, key=f"kw_{t}")]

    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state["run_sweep"] = True
        st.session_state["sweep_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_event("SWEEP", f"targets={selected_targets} sites={active_sites}")

    conn.close()

# ---------------- MAIN ----------------
t_live, t_arch, t_jobs, t_logs = st.tabs(
    ["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"]
)

# ---------------- LIVE FEED ----------------
with t_live:
    if st.session_state.get("run_sweep"):
        with st.status("🔎 Searching via Google…") as status:
            conn = get_db()
            total = 0

            for site in active_sites:
                for kw in selected_targets:
                    rows = google_serpapi_dork(kw, site)
                    if rows:
                        conn.executemany(
                            """
                            INSERT OR IGNORE INTO items
                            (found_date, target, source, title, price, url)
                            VALUES (?,?,?,?,?,?)
                            """,
                            rows
                        )
                        conn.commit()
                        total += len(rows)

            df = pd.read_sql_query(
                """
                SELECT found_date, target, source, title, price, url
                FROM items
                WHERE found_date >= ?
                ORDER BY found_date DESC
                """,
                conn,
                params=(st.session_state["sweep_ts"],)
            )
            conn.close()

            status.update(label=f"Found {total} results", state="complete")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={"url": st.column_config.LinkColumn("URL")}
        )

        st.session_state["run_sweep"] = False
    else:
        st.info("Ready.")

# ---------------- ARCHIVE ----------------
with t_arch:
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC", conn)
    conn.close()
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={"url": st.column_config.LinkColumn("URL")}
    )

# ---------------- JOBS ----------------
with t_jobs:
    st.subheader("📡 Add Site (Google Search)")
    with st.form("add_site", clear_on_submit=True):
        ns = st.text_input("Domain (e.g. vintage-computer.com)")
        if st.form_submit_button("Add Site") and ns:
            conn = get_db()
            conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (ns,))
            conn.commit()
            conn.close()
            log_event("CONFIG", f"Added site '{ns}'")
            st.rerun()

# ---------------- LOGS ----------------
with t_logs:
    col1, col2 = st.columns([3, 1])

    with col2:
        debug = st.toggle("Debug Mode", value=(st.session_state["log_level"] == logging.DEBUG))
        st.session_state["log_level"] = logging.DEBUG if debug else logging.INFO
        logging.getLogger().setLevel(st.session_state["log_level"])

        if st.button("🧹 Purge Logs"):
            open(LOG_FILE, "w").close()
            st.rerun()

    with col1:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                st.code("".join(f.readlines()[-300:]))
