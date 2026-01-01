# ============================================================
# SCOUT – Intelligence Terminal
# VERSION: 3.73
#
# STABILITY RESTORE (NO REGRESSIONS):
# - Jobs UI restored (name, frequency, keywords, save)
# - Config UI restored (add/delete sites + keywords)
# - Logs restored (debug toggle + purge + tail)
# - Sidebar lists are fixed-height, bordered, scrollable
# - Live Feed has Google engine toggle (authoritative)
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

if "google_enabled" not in st.session_state:
    st.session_state["google_enabled"] = True

logging.basicConfig(
    filename=LOG_FILE,
    level=st.session_state["log_level"],
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def log_event(tag: str, msg: str, level=logging.INFO) -> None:
    logging.log(level, f"[{tag.upper()}] {msg}")

def get_db():
    return sqlite3.connect("scout.db", check_same_thread=False)

def db_list_sites(conn) -> list[str]:
    try:
        return pd.read_sql_query("SELECT domain FROM custom_sites ORDER BY domain", conn)["domain"].tolist()
    except Exception:
        return []

def db_list_keywords(conn) -> list[str]:
    try:
        return pd.read_sql_query("SELECT name FROM targets ORDER BY name", conn)["name"].tolist()
    except Exception:
        return []

# ---------------- COLLECTOR ----------------
def google_serpapi_dork(keyword: str, domain: str) -> list[tuple]:
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

# ---------------- SIDEBAR (SCOPE + EXECUTE) ----------------
with st.sidebar:
    st.title("🛡️ SCOUT")
    st.caption("Ad-hoc scope")

    conn = get_db()

    st.subheader("📡 Sites")
    sites = db_list_sites(conn)
    with st.container(height=170, border=True):
        active_sites = [
            s for s in sites
            if st.toggle(s, value=True, key=f"sb_site_{s}")
        ]

   st.subheader("🎯 Keywords")

with st.container(height=210, border=True):
    # Quick add keyword (ad-hoc convenience)
    with st.form("quick_add_kw", clear_on_submit=True):
        c1, c2 = st.columns([4, 1])
        new_kw = c1.text_input("Add keyword", label_visibility="collapsed")
        add = c2.form_submit_button("＋")
        if add and new_kw:
            conn.execute(
                "INSERT OR IGNORE INTO targets (name) VALUES (?)",
                (new_kw.strip(),)
            )
            conn.commit()
            log_event("KEYWORD", f"Added keyword '{new_kw}' from sidebar")
            st.rerun()

    st.divider()

    keywords = db_list_keywords(conn)
    active_keywords = [
        k for k in keywords
        if st.checkbox(k, value=True, key=f"sb_kw_{k}")
    ]


    st.divider()

    if st.button("🚀 EXECUTE SWEEP", type="primary", width="stretch"):
        st.session_state["run_sweep"] = True
        st.session_state["sweep_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state["last_scope"] = {
            "sites": active_sites,
            "keywords": active_keywords,
        }
        log_event("SWEEP", f"Ad-hoc sweep requested sites={active_sites} keywords={active_keywords}")

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

        st.session_state["google_enabled"] = st.toggle(
            "Google (SerpAPI)",
            value=st.session_state["google_enabled"],
            help="Enable/disable Google site-based searches for ad-hoc runs.",
        )

        st.toggle("eBay (Planned)", value=False, disabled=True)
        st.toggle("Amazon (Planned)", value=False, disabled=True)
        st.toggle("Etsy (Planned)", value=False, disabled=True)

        st.divider()
        st.subheader("📊 Status")
        st.markdown("**Version:** 3.72")

        if "sweep_ts" in st.session_state:
            scope = st.session_state.get("last_scope", {})
            st.markdown(f"**Last Run:** {st.session_state['sweep_ts']}")
            st.markdown(f"**Google Enabled:** {st.session_state['google_enabled']}")
            st.markdown(f"**Sites:** {len(scope.get('sites', []))}")
            st.markdown(f"**Keywords:** {len(scope.get('keywords', []))}")
        else:
            st.markdown("**Last Run:** —")

        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                st.divider()
                st.caption("Last log line")
                st.code(lines[-1].strip() if lines else "Ready.")
            except Exception:
                pass

    with left:
        if st.session_state.get("run_sweep"):
            scope = st.session_state.get("last_scope", {"sites": [], "keywords": []})

            if not st.session_state["google_enabled"]:
                st.warning("Google is disabled. No engines enabled, so nothing will run.")
                log_event("SWEEP", "Aborted: Google disabled; no engines enabled.")
                st.session_state["run_sweep"] = False
            elif not scope["sites"] or not scope["keywords"]:
                st.warning("Select at least one site and one keyword.")
                log_event("SWEEP", "Aborted: missing sites or keywords.")
                st.session_state["run_sweep"] = False
            else:
                log_event("SWEEP", f"Ad-hoc sweep started engine=google sites={scope['sites']} keywords={scope['keywords']}")
                with st.status("🔎 Searching…") as status:
                    conn = get_db()
                    inserted = 0

                    for site in scope["sites"]:
                        for kw in scope["keywords"]:
                            try:
                                rows = google_serpapi_dork(kw, site)
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
                                log_event("ERROR", f"Collector failure site={site} kw={kw} err={e}", level=logging.ERROR)

                    # Show only results from this run timestamp
                    df = pd.read_sql_query(
                        """
                        SELECT found_date, target, source, title, price, url
                        FROM items
                        WHERE found_date >= ?
                        ORDER BY found_date DESC
                        """,
                        conn,
                        params=(st.session_state["sweep_ts"],),
                    )
                    conn.close()

                    log_event("ENGINE", f"Inserted {inserted} items (duplicates ignored).")
                    status.update(label=f"Sweep complete: {len(df)} items returned.", state="complete")

                st.dataframe(
                    df,
                    width="stretch",
                    hide_index=True,
                    column_config={"url": st.column_config.LinkColumn("URL")},
                )

                st.session_state["run_sweep"] = False
        else:
            st.info("Ready. Select sites/keywords in the sidebar and execute.")

# ---------------- ARCHIVE ----------------
with t_arch:
    st.subheader("📜 Historical Findings")
    conn = get_db()
    try:
        df = pd.read_sql_query("SELECT * FROM items ORDER BY found_date DESC", conn)
    finally:
        conn.close()

    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={"url": st.column_config.LinkColumn("URL")},
    )

# ---------------- JOBS ----------------
with t_jobs:
    st.header("🗓 Scheduled Jobs")

    # Restore original scheduling UI (no execution wiring yet)
    conn = get_db()
    try:
        all_keywords = db_list_keywords(conn)
    finally:
        conn.close()

    with st.form("schedule_form_v372", clear_on_submit=True):
        jn = st.text_input("Job Name")
        jf = st.selectbox("Frequency", ["6 Hours", "12 Hours", "Daily"])
        jt = st.multiselect("Keywords", all_keywords)

        if st.form_submit_button("Save Job"):
            if not jn or not jt:
                st.warning("Job Name and at least one Keyword are required.")
            else:
                conn = get_db()
                try:
                    conn.execute(
                        """
                        INSERT INTO schedules (job_name, frequency, target_list)
                        VALUES (?,?,?)
                        """,
                        (jn, jf, ",".join(jt)),
                    )
                    conn.commit()
                    log_event("SCHEDULER", f"Saved job '{jn}' ({jf}) targets={jt}")
                finally:
                    conn.close()
                st.rerun()

    st.divider()

    # Additive: show saved jobs (does not remove anything)
    st.subheader("Saved Jobs")
    conn = get_db()
    try:
        jobs_df = pd.read_sql_query(
            "SELECT rowid as id, job_name, frequency, target_list FROM schedules ORDER BY rowid DESC",
            conn,
        )
    except Exception:
        jobs_df = pd.DataFrame(columns=["id", "job_name", "frequency", "target_list"])
    finally:
        conn.close()

    if jobs_df.empty:
        st.caption("No jobs saved yet.")
    else:
        for _, row in jobs_df.iterrows():
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{row['job_name']}** — {row['frequency']} — {row['target_list']}")
            if c2.button("🗑️", key=f"job_del_{row['id']}"):
                conn = get_db()
                try:
                    conn.execute("DELETE FROM schedules WHERE rowid = ?", (int(row["id"]),))
                    conn.commit()
                    log_event("SCHEDULER", f"Deleted job id={row['id']} name='{row['job_name']}'")
                finally:
                    conn.close()
                st.rerun()

# ---------------- CONFIG ----------------
with t_cfg:
    st.header("⚙️ Configuration")

    st.subheader("📡 Manage Sites")
    conn = get_db()
    try:
        sites_df = pd.read_sql_query("SELECT domain FROM custom_sites ORDER BY domain", conn)
    except Exception:
        sites_df = pd.DataFrame(columns=["domain"])

    if sites_df.empty:
        st.caption("No custom sites registered yet.")
    else:
        for s in sites_df["domain"]:
            c1, c2 = st.columns([5, 1])
            c1.write(s)
            if c2.button("🗑️", key=f"cfg_site_del_{s}"):
                conn.execute("DELETE FROM custom_sites WHERE domain = ?", (s,))
                conn.commit()
                log_event("CONFIG", f"Deleted site '{s}'")
                st.rerun()

    with st.form("cfg_add_site_v372", clear_on_submit=True):
        ns = st.text_input("Add Site (e.g. vintage-computer.com)")
        if st.form_submit_button("Add Site"):
            if ns:
                conn.execute("INSERT OR IGNORE INTO custom_sites (domain) VALUES (?)", (ns,))
                conn.commit()
                log_event("CONFIG", f"Added site '{ns}'")
                st.rerun()

    st.divider()

    st.subheader("🎯 Manage Keywords")
    try:
        kw_df = pd.read_sql_query("SELECT name FROM targets ORDER BY name", conn)
    except Exception:
        kw_df = pd.DataFrame(columns=["name"])

    if kw_df.empty:
        st.caption("No keywords registered yet.")
    else:
        for k in kw_df["name"]:
            c1, c2 = st.columns([5, 1])
            c1.write(k)
            if c2.button("🗑️", key=f"cfg_kw_del_{k}"):
                conn.execute("DELETE FROM targets WHERE name = ?", (k,))
                conn.commit()
                log_event("CONFIG", f"Deleted keyword '{k}'")
                st.rerun()

    with st.form("cfg_add_kw_v372", clear_on_submit=True):
        nk = st.text_input("Add Keyword")
        if st.form_submit_button("Add Keyword"):
            if nk:
                conn.execute("INSERT OR IGNORE INTO targets (name) VALUES (?)", (nk,))
                conn.commit()
                log_event("CONFIG", f"Added keyword '{nk}'")
                st.rerun()

    conn.close()

# ---------------- LOGS ----------------
with t_logs:
    st.subheader("🛠️ System Logs")

    col1, col2 = st.columns([3, 1])

    with col2:
        debug = st.toggle("Debug Mode", value=(st.session_state["log_level"] == logging.DEBUG))
        st.session_state["log_level"] = logging.DEBUG if debug else logging.INFO
        logging.getLogger().setLevel(st.session_state["log_level"])

        if st.button("🧹 Purge Logs"):
            open(LOG_FILE, "w").close()
            log_event("LOG", "Logs purged")
            st.rerun()

    with col1:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                st.code("".join(f.readlines()[-300:]))
        else:
            st.caption("No log file yet.")
