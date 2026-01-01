# ============================================================
# SCOUT – Intelligence Terminal
# VERSION: 3.73
#
# FIXES:
# - Google toggle no longer disables custom-site searches
# - Archive now shows newest results at TOP
# - No functionality removed
# ============================================================

import os
import logging
import sqlite3
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# ---------------- SYSTEM CORE ----------------
st.set_page_config(page_title="SCOUT | Intelligence Terminal", layout="wide")

LOG_FILE = "scout.log"
SERPAPI_KEY = st.secrets.get("SERPAPI_KEY")

if not SERPAPI_KEY:
    st.error("SERPAPI_KEY not found in .streamlit/secrets.toml")
    st.stop()

if "log_level" not in st.session_state:
    st.session_state["log_level"] = logging.INFO

if "google_store_enabled" not in st.session_state:
    st.session_state["google_store_enabled"] = True  # future use

logging.basicConfig(
    filename=LOG_FILE,
    level=st.session_state["log_level"],
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def log_event(tag, msg, level=logging.INFO):
    logging.log(level, f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

def list_sites(conn):
    return pd.read_sql_query(
        "SELECT domain FROM custom_sites ORDER BY domain", conn
    )["domain"].tolist()

def list_keywords(conn):
    return pd.read_sql_query(
        "SELECT name FROM targets ORDER BY name", conn
    )["name"].tolist()

# ---------------- COLLECTOR ----------------
def google_dork(keyword, domain):
    query = f"site:{domain} {keyword}"
    log_event("COLLECTOR", f"Google dork: {query}")

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": 10,
    }

    r = requests.get("https://serpapi.com/search", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []

    for res in data.get("organic_results", []):
        rows.append(
            (ts, keyword, domain, res.get("title"), None, res.get("link"))
        )

    log_event("COLLECTOR", f"{len(rows)} results for {query}")
    return rows

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.title("🛡️ SCOUT")
    st.caption("Ad-hoc scope")

    conn = get_db()

    st.subheader("📡 Sites")
    with st.container(height=170, border=True):
        sites = list_sites(conn)
        active_sites = [
            s for s in sites
            if st.toggle(s, value=True, key=f"site_{s}")
        ]

    st.subheader("🎯 Keywords")
    with st.container(height=210, border=True):
        with st.form("quick_add_kw", clear_on_submit=True):
            c1, c2 = st.columns([4, 1])
            new_kw = c1.text_input("Add keyword", label_visibility="collapsed")
            add = c2.form_submit_button("＋")
            if add and new_kw:
                conn.execute(
                    "INSERT OR IGNORE INTO targets (name) VALUES (?)",
                    (new_kw.strip(),),
                )
                conn.commit()
                log_event("KEYWORD", f"Added keyword '{new_kw}'")
                st.rerun()

        st.divider()

        keywords = list_keywords(conn)
        active_keywords = [
            k for k in keywords
            if st.checkbox(k, value=True, key=f"kw_{k}")
        ]

    st.divider()

    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state["run_sweep"] = True
        st.session_state["run_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state["scope"] = {
            "sites": active_sites,
            "keywords": active_keywords,
        }
        log_event(
            "SWEEP",
            f"Requested sites={active_sites} keywords={active_keywords}",
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
        st.subheader("🔍 Search Engines")

        st.session_state["google_store_enabled"] = st.toggle(
            "Google Store (future)",
            value=st.session_state["google_store_enabled"],
            help="Controls Google-owned properties only. Custom sites always use Google dorking.",
        )

        st.toggle("eBay (Planned)", value=False, disabled=True)
        st.toggle("Amazon (Planned)", value=False, disabled=True)
        st.toggle("Etsy (Planned)", value=False, disabled=True)

        st.divider()
        st.subheader("📊 Status")
        st.markdown("**Version:** 3.73")

        if "run_ts" in st.session_state:
            s = st.session_state["scope"]
            st.markdown(f"**Last Run:** {st.session_state['run_ts']}")
            st.markdown(f"**Sites:** {len(s['sites'])}")
            st.markdown(f"**Keywords:** {len(s['keywords'])}")
        else:
            st.markdown("**Last Run:** —")

    with left:
        if st.session_state.get("run_sweep"):
            scope = st.session_state["scope"]

            if not scope["sites"] or not scope["keywords"]:
                st.warning("Select at least one site and one keyword.")
                st.session_state["run_sweep"] = False
            else:
                with st.status("🔎 Searching…") as status:
                    conn = get_db()
                    inserted = 0

                    for site in scope["sites"]:
                        for kw in scope["keywords"]:
                            try:
                                rows = google_dork(kw, site)
                                if rows:
                                    conn.executemany(
                                        """
                                        INSERT OR IGNORE INTO items
                                        (found_date, target, source, title, price, url)
                                        VALUES (?,?,?,?,?,?)
                                        """,
                                        rows,
                                    )
                                    conn.commit()
                                    inserted += len(rows)
                            except Exception as e:
                                log_event("ERROR", f"{site}/{kw}: {e}", logging.ERROR)

                    df = pd.read_sql_query(
                        """
                        SELECT found_date, target, source, title, price, url
                        FROM items
                        WHERE found_date >= ?
                        ORDER BY found_date DESC
                        """,
                        conn,
                        params=(st.session_state["run_ts"],),
                    )
                    conn.close()

                    log_event("ENGINE", f"Inserted {inserted} items")
                    status.update(
                        label=f"Sweep complete: {len(df)} items",
                        state="complete",
                    )

                st.dataframe(
                    df,
                    width="stretch",
                    hide_index=True,
                    column_config={"url": st.column_config.LinkColumn("URL")},
                )

                st.session_state["run_sweep"] = False
        else:
            st.info("Ready.")

# ---------------- ARCHIVE ----------------
with t_arch:
    st.subheader("📜 Historical Findings")
    conn = get_db()
    df = pd.read_sql_query(
        "SELECT * FROM items ORDER BY found_date DESC", conn
    )
    conn.close()

    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={"url": st.column_config.LinkColumn("URL")},
    )

# ---------------- JOBS ----------------
with t_jobs:
    st.header("🗓 Scheduled Jobs (UI only)")

    conn = get_db()
    all_keywords = list_keywords(conn)
    conn.close()

    with st.form("job_form"):
        jn = st.text_input("Job Name")
        jf = st.selectbox("Frequency", ["6 Hours", "12 Hours", "Daily"])
        jt = st.multiselect("Keywords", all_keywords)

        if st.form_submit_button("Save Job"):
            if jn and jt:
                conn = get_db()
                conn.execute(
                    """
                    INSERT INTO schedules (job_name, frequency, target_list)
                    VALUES (?,?,?)
                    """,
                    (jn, jf, ",".join(jt)),
                )
                conn.commit()
                conn.close()
                log_event("SCHEDULER", f"Saved job '{jn}'")
                st.rerun()

# ---------------- CONFIG ----------------
with t_cfg:
    st.header("⚙️ Configuration")

    conn = get_db()

    st.subheader("📡 Sites")
    for s in list_sites(conn):
        c1, c2 = st.columns([5, 1])
        c1.write(s)
        if c2.button("🗑️", key=f"del_site_{s}"):
            conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
            conn.commit()
            log_event("CONFIG", f"Deleted site '{s}'")
            st.rerun()

    with st.form("add_site"):
        ns = st.text_input("Add Site")
        if st.form_submit_button("Add") and ns:
            conn.execute(
                "INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)",
                (ns,),
            )
            conn.commit()
            log_event("CONFIG", f"Added site '{ns}'")
            st.rerun()

    st.divider()

    st.subheader("🎯 Keywords")
    for k in list_keywords(conn):
        c1, c2 = st.columns([5, 1])
        c1.write(k)
        if c2.button("🗑️", key=f"del_kw_{k}"):
            conn.execute("DELETE FROM targets WHERE name = ?", (k,))
            conn.commit()
            log_event("CONFIG", f"Deleted keyword '{k}'")
            st.rerun()

    conn.close()

# ---------------- LOGS ----------------
with t_logs:
    col1, col2 = st.columns([3, 1])

    with col2:
        debug = st.toggle(
            "Debug Mode",
            value=(st.session_state["log_level"] == logging.DEBUG),
        )
        st.session_state["log_level"] = (
            logging.DEBUG if debug else logging.INFO
        )
        logging.getLogger().setLevel(st.session_state["log_level"])

        if st.button("🧹 Purge Logs"):
            open(LOG_FILE, "w").close()
            log_event("LOG", "Logs purged")
            st.rerun()

    with col1:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                st.code("".join(f.readlines()[-300:]))
