import sqlite3
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import smtplib
from email.message import EmailMessage
import os

# CONFIGURATION
DB_NAME = "scout.db"
TARGETS = ["Texas Ranger silver peso", "OHP obsolete oval patch", "WHCA challenge coin"]
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS items 
                 (id INTEGER PRIMARY KEY, 
                  found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  target TEXT, title TEXT, price TEXT, url TEXT UNIQUE)''')
    conn.commit()
    conn.close()

def scrape_ebay(query):
    # (Existing scraping logic from previous steps)
    results = []
    # ... BeautifulSoup logic ...
    return results

def run_agent():
    init_db()
    conn = sqlite3.connect(DB_NAME)
    new_finds = []

    for target in TARGETS:
        listings = scrape_ebay(target)
        for item in listings:
            try:
                conn.execute("INSERT INTO items (target, title, price, url) VALUES (?, ?, ?, ?)",
                             (target, item['title'], item['price'], item['link']))
                new_finds.append(item)
            except sqlite3.IntegrityError:
                continue # Already in DB
    
    conn.commit()
    
    # REPORTING LOGIC
    if new_finds:
        send_alert(new_finds, "Daily Scout Alert")
        
    if datetime.now().weekday() == 6: # Sunday
        weekly_data = pd.read_sql_query("SELECT * FROM items WHERE found_date > datetime('now', '-7 days')", conn)
        send_alert(weekly_data.to_dict('records'), "Weekly Intelligence Roll-up")
    
    # 90-DAY PURGE
    conn.execute("DELETE FROM items WHERE found_date < datetime('now', '-90 days')")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    run_agent()
