# SCOUT TERMINAL VERSION: 3.50
# FIXES:
# - Restore log purge
# - Add DEBUG mode toggle
# - Expand logging when DEBUG enabled

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import logging
from datetime import datetime

# ---------------- SYSTEM CORE ----------------
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

LOG_FILE = "scout.log"

# Initialize logging once
if "log_level" not in st.session_state:
    st.session_state["log_level"] = logging.INFO

logging.basicConfig(
    filename=LOG_FILE,
    level=st.session_state["log_level"],
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def set_log_level(level):
    logging.getLogger().setLevel(level)
    st.session_state["log_level"] = level

def log_event(tag, msg, level=logging.INFO):
    logging.log(level, f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

# ---------------- COLLECTOR (STUB) ----------------
def fake_search(targets, sources):
    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_event("DEBUG", f"fake_search targets={targets}, sources={sources}", logging.DEBUG)

    for src in sources:
        for t in targets:
            rows.append((
                now,
                t,
                src,
                f"{t} listing on {src}",
                "$199.99",
                f"https://{src}/search?q={t}"
            ))
    return rows

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.title("🛡️ SCOUT v3.50")

    # ---- Logging controls ----
    st.subheader("📝 Logging")

    debug_mode = st.toggle("Debug Mode", value=(st.session_state["log_level"] == logging.DEBUG))
    if debug_mode:
        set_log_level(logging.DEBUG)
        log_event("LOG", "Debug logging enabled", logging.DEBUG)
    else:
        set_log_level(logging.INFO)

    if st.button("🧹 Purge Logs", width="stretch"):
        if os.path.exists(LOG_FILE):
            open(LOG_FILE, "w").close()
            log_event("LOG", "Logs purged")
        st.rerun()

    st.divider()

    conn = get_db()

    # Global engines
    st.subheader("🌐 Global Engines")
    use_ebay = st.toggle("eBay", value=True)
    use_google = st.toggle("Google", value=True)
    use_etsy = st.toggle("Etsy", value=True)

    engine_sources = []
    if use_ebay: engine_sources.append("ebay.com")
    if use_google: engine_sources.append("google.com")
    if use_etsy: engine_sources.append("etsy.com")

    st.divider()

    # Custom sites
    st.subheader("📡 Custom Sites")
    c_list = pd.read_sql_query("SELECT domain FROM custom_sites", conn)["domain"].tolist()
    active_customs = [s for s in c_list if st.toggle(s, value=True, key=f"site_{s}")]

    active_sources = engine_sources + active_customs
    log_event("DEBUG", f"Active sources={active_sources}", logging.DEBUG)

    st.divider()

    # Keywords
    with st.expander("🎯 Keyword Library", expanded=True):
        with st.form("add_keyword", clear_on_submit=True):
            nk = st.text_input("New Target")
            if st.form_submit_button("＋"):
                if nk:
                    conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nk,))
                    conn.commit()
                    log_event("CONFIG", f"Added keyword '{nk}'")
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
                log_event("CONFIG", f"Deleted keyword '{t}'")
                st.rerun()

    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state["run_sweep"] = True
        st.session_state["sweep_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_event(
            "SWEEP",
            f"Started targets={selected_targets}, sources={active_sources}"
        )

    conn.close()

# ---------------- MAIN UI ----------------
t_live, t_arch, t_jobs, t_logs = st.tabs(
    ["📡 Live Feed", "📜 Archive", "⚙️ Jobs & Config", "📝 Logs"]
)

# ---------------- LIVE FEED ----------------
with t_live:
    if st.session_state.get("run_sweep"):
        with st.status("📡 Sweeping…") as status:
            conn = get_db()

            rows = fake_search(selected_targets, active_sources)

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
            status.update(label=f"Sweep complete: {len(df)} new items", state="complete")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={"url": st.column_config.LinkColumn("URL")}
        )

        st.session_state["run_sweep"] = False
    else:
        st.info("Terminal ready.")

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

    st.subheader("📡 Register New Site")
    with st.form("add_site", clear_on_submit=True):
        ns = st.text_input("Domain (e.g. newegg.com)")
        if st.form_submit_button("Add Site"):
            if ns:
                conn = get_db()
                conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (ns,))
                conn.commit()
                conn.close()
                log_event("CONFIG", f"Added site '{ns}'")
                st.rerun()

    st.divider()

    st.subheader("📅 Schedule Search")
    with st.form("schedule_form"):
        jn = st.text_input("Job Name")
        jt = st.multiselect("Keywords", t_list)
        jf = st.selectbox("Frequency", ["6 Hours", "12 Hours", "Daily"])
        if st.form_submit_button("Save Job"):
            if jn and jt:
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
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            st.code("".join(f.readlines()[-300:]))
