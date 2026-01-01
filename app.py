# ============================================================
# SCOUT – Intelligence Terminal
# VERSION: 3.63
#
# STATUS:
# - Google Search via SerpAPI: ENABLED
# - eBay Marketplace (SerpAPI): PLANNED
# - Amazon Marketplace (SerpAPI): PLANNED
# - Etsy Marketplace (SerpAPI): PLANNED
#
# NOTES:
# - Google is the only active engine
# - Engines are configurable in Jobs & Config
# - Sidebar is limited to execution controls
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

# ---------------- SIDEBAR (EXECUTION ONLY) ----------------
with st.sidebar:
    st.title("🛡️ SCOUT v3.63")

    conn = get_db()

    st.subheader("📡 Sites (Google)")
    sites = pd.read_sql_query("SELECT domain FROM custom_sites", conn)["domain"].tolist()
    active_sites = [s for s in sites if st.toggle(s, value=True, key=f"site_{s}")]

    st.divider()

    st.subheader("🎯 Keywords")
    t_list = pd.read_sql_query("SELECT name FROM targets", conn)["name"].tolist()
    selected_targets = [t for t in t_list if st.checkbox(t, value=True, key=f"kw_{t}")]

    st.divider()

    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state["run_sweep"] = True
        st.session_state["sweep_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_event("SWEEP", f"targets={selected_targets} sites={active_sites}")

    conn.close()

# ---------------- MAIN TABS ----------------
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

# ---------------- JOBS & CONFIG ----------------
with t_jobs:
    st.header("⚙️ Jobs & Config")

    # ---- Engines ----
    st.subheader("🔍 Search Engines (SerpAPI)")
    st.toggle("Google (site-based)", value=True, disabled=False)
    st.toggle("eBay Marketplace", value=False, disabled=True, help="Planned")
    st.toggle("Amazon Marketplace", value=False, disabled=True, help="Planned")
    st.toggle("Etsy Marketplace", value=False, disabled=True, help="Planned")

    st.divider()

    # ---- Sites ----
    st.subheader("📡 Manage Sites")
    conn = get_db()
    sites_df = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
    for s in sites_df["domain"]:
        c1, c2 = st.columns([5, 1])
        c1.write(s)
        if c2.button("🗑️", key=f"del_site_{s}"):
            conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
            conn.commit()
            log_event("CONFIG", f"Deleted site '{s}'")
            st.rerun()

    with st.form("add_site", clear_on_submit=True):
        ns = st.text_input("Add new site")
        if st.form_submit_button("Add Site") and ns:
            conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (ns,))
            conn.commit()
            log_event("CONFIG", f"Added site '{ns}'")
            st.rerun()

    conn.close()

    st.divider()

    # ---- Keywords ----
    st.subheader("🎯 Manage Keywords")
    conn = get_db()
    kw_df = pd.read_sql_query("SELECT name FROM targets", conn)
    for k in kw_df["name"]:
        c1, c2 = st.columns([5, 1])
        c1.write(k)
        if c2.button("🗑️", key=f"del_kw_{k}"):
            conn.execute("DELETE FROM targets WHERE name = ?", (k,))
            conn.commit()
            log_event("CONFIG", f"Deleted keyword '{k}'")
            st.rerun()

    with st.form("add_keyword", clear_on_submit=True):
        nk = st.text_input("Add new keyword")
        if st.form_submit_button("Add Keyword") and nk:
            conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nk,))
            conn.commit()
            log_event("CONFIG", f"Added keyword '{nk}'")
            st.rerun()

    conn.close()

    st.divider()

    # ---- Scheduler ----
    st.subheader("📅 Schedule Search")
    with st.form("schedule_form"):
        jn = st.text_input("Job Name")
        jf = st.selectbox("Frequency", ["6 Hours", "12 Hours", "Daily"])
        jt = st.multiselect("Keywords", t_list)
        if st.form_submit_button("Save Job") and jn and jt:
            conn = get_db()
            conn.execute(
                "INSERT INTO schedules (job_name, frequency, target_list) VALUES (?,?,?)",
                (jn, jf, ",".join(jt))
            )
            conn.commit()
            conn.close()
            log_event("SCHEDULER", f"Saved job '{jn}' ({jf})")
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
