import sqlite3
import pandas as pd
from datetime import datetime, timedelta

DB_NAME = "scout.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Unique URL prevents duplicate entries
    c.execute('''CREATE TABLE IF NOT EXISTS items 
                 (id INTEGER PRIMARY KEY, 
                  found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  target TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    conn.commit()
    conn.close()

def scout_logic():
    # ... (Your eBay scraping code here) ...
    # After scraping new items:
    save_to_db(new_items_list)
    
    # Check what day it is
    today = datetime.now()
    
    # 1. ALWAYS send the Daily Alert for brand new finds
    send_daily_alert(new_items_list)
    
    # 2. SUNDAY ROLL-UP: If it's Sunday (weekday 6), send the intelligence report
    if today.weekday() == 6:
        send_weekly_rollup()

def send_weekly_rollup():
    conn = sqlite3.connect(DB_NAME)
    # Pull everything from the last 7 days
    query = "SELECT target, title, price, url FROM items WHERE found_date > datetime('now', '-7 days')"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        # Convert the table to a clean HTML table for the email
        html_table = df.to_html(index=False, classes='mystyle')
        email_body = f"<h2>🛡️ Weekly Intelligence Report</h2><p>Here are all opportunities found in the last 7 days:</p>{html_table}"
        # ... (Send email code) ...

def purge_old_data():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Keep only the last 90 days
    c.execute("DELETE FROM items WHERE found_date < datetime('now', '-90 days')")
    conn.commit()
    conn.close()
