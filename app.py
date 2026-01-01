# ============================================================
# SCOUT – Intelligence Terminal
# VERSION: 3.67
#
# FINALIZED UI MODEL:
# - Sidebar: Engines + Scope + Execute
# - Live Feed: Results + Status pane (read-only)
# - Jobs / Config / Logs separated
#
# ACTIVE ENGINE:
# - Google Search via SerpAPI (toggleable)
#
# PLANNED:
# - eBay, Amazon, Etsy (SerpAPI)
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

    return rows

# ---------------- SIDEBAR (ENGINES + SCOPE) ----------------
with st.sidebar:
    st.title("🛡️ SCOUT")
    st.caption("Ad-hoc search scope")

    st.subheader("🔍 Search Engines")

    google_enabled = st.toggle(
        "Google (SerpAPI)",
        value=True,
        help="Site-based Google searches via SerpAPI"
    )

    st.toggle("eBay Marketplace", value=False, disabled=True, help="Planned")
    st.toggle("Amazon Marketplace", value=False, disabled=True, help="Planned")
    st.toggle("Etsy Marketplace", value=False, disabled=True, help="Planned")

    st.divider()

    conn = get_db()

    st.subheader("📡 Sites")
    sites = pd.read_sql_query("SELECT domain FROM custom_sites", conn)["domain"].tolist()
    active_sites = [s for s in sites if st.toggle(s, value=True, key=f"sb_site_{s}")]

    st.divider()

    st.subheader("🎯 Keywords")
    keywords = pd.read_sql_query("SELECT name FROM targets", conn)["name"].tolist()
    active_keywords = [k for k in keywords if st.checkbox(k, value=True, key=f"sb_kw_{k}")]

    st.divider()

    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        if not google_enabled:
            st.warning("No search engines enabled.")
        else:
            st.session_state["run_sweep"] = True
            st.session_state["sweep_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state["last_scope"] = {
                "engine": "Google",
                "sites": active_sites,
                "keywords": active_keywords
            }
            log_event(
                "SWEEP",
                f"engine=google sites={active_sites} keywords={active_keywords}"
            )

    conn.close()

# ---------------- MAIN TABS ----------------
t_live, t_arch, t_jobs, t_cfg, t_logs = st.tabs(
    ["📡 Live Feed", "📜 Archive", "🗓 Jobs", "⚙️ Config", "📝 Logs"]
)

# ---------------- LIVE FEED ----------------
with t_live:
    left, right = st.columns([3, 1])

    with right:
        st.subheader("📊 Run Status")
        st.markdown("**Version:** 3.67")

        if google_enabled:
            st.markdown("**Engine:** Google (SerpAPI)")
        else:
            st.markdown("**Engine:** —")

        if "sweep_ts" in st.session_state:
            scope = st.session_state.get("last_scope", {})
            st.markdown(f"**Last Run:** {st.session_state['sweep_ts']}")
            st.markdown(f"**Sites:** {len(scope.get('sites', []))}")
            st.markdown(f"**Keywords:** {len(scope.get('keywords', []))}")
        else:
            st.markdown("**Last Run:** —")

    with left:
        if st.session_state.get("run_sweep"):
            with st.status("🔎 Searching…") as status:
                conn = get_db()
                total = 0

                if google_enabled:
                    for site in active_sites:
                        for kw in active_keywords:
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

                status.update(label=f"Found {total} items", state="complete")

            st.dataframe(
                df,
                width="stretch",
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
        width="stretch",
        hide_index=True,
        column_config={"url": st.column_config.LinkColumn("URL")}
    )

# ---------------- JOBS ----------------
with t_jobs:
    st.header("🗓 Scheduled Jobs")
    st.info("Scheduler execution wiring pending (UI complete).")

# ---------------- CONFIG ----------------
with t_cfg:
    st.header("⚙️ Configuration")

    st.subheader("📡 Manage Sites")
    conn = get_db()
    sites_df = pd.read_sql_query("SELECT domain FROM custom_sites", conn)
    for s in sites_df["domain"]:
        c1, c2 = st.columns([5, 1])
        c1.write(s)
        if c2.button("🗑️", key=f"cfg_site_{s}"):
            conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
            conn.commit()
            st.rerun()

    with st.form("add_site", clear_on_submit=True):
        ns = st.text_input("Add Site")
        if st.form_submit_button("Add") and ns:
            conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (ns,))
            conn.commit()
            st.rerun()

    st.divider()

    st.subheader("🎯 Manage Keywords")
    kw_df = pd.read_sql_query("SELECT name FROM targets", conn)
    for k in kw_df["name"]:
        c1, c2 = st.columns([5, 1])
        c1.write(k)
        if c2.button("🗑️", key=f"cfg_kw_{k}"):
            conn.execute("DELETE FROM targets WHERE name = ?", (k,))
            conn.commit()
            st.rerun()

    with st.form("add_kw", clear_on_submit=True):
        nk = st.text_input("Add Keyword")
        if st.form_submit_button("Add") and nk:
            conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nk,))
            conn.commit()
            st.rerun()

    conn.close()

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
