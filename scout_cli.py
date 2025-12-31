import requests
from bs4 import BeautifulSoup
import smtplib
import os
import csv
from email.message import EmailMessage

# 1. SETUP - Targets & Email
TARGETS = ["Texas Ranger silver peso", "OHP obsolete oval patch", "WHCA challenge coin"]
EMAIL_ADDRESS = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASS') # Use App Password
HISTORY_FILE = "last_seen.csv"

def get_listings(query):
    url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=10"
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    items = []
    for item in soup.select('.s-item__info')[1:6]:
        title = item.select_one('.s-item__title').text
        link = item.select_one('.s-item__link')['href']
        price = item.select_one('.s-item__price').text
        items.append({'title': title, 'link': link, 'price': price})
    return items

def run_scout():
    new_finds = []
    # Load history
    seen_links = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            seen_links = set(line.strip() for line in f)

    for target in TARGETS:
        listings = get_listings(target)
        for l in listings:
            if l['link'] not in seen_links:
                new_finds.append(l)
                seen_links.add(l['link'])

    if new_finds:
        # Save new history
        with open(HISTORY_FILE, 'w') as f:
            for link in seen_links:
                f.write(link + '\n')
        
        # Build Email Content
        msg_content = "Scout Alert: New Items Found!\n\n"
        for item in new_finds:
            msg_content += f"Item: {item['title']}\nPrice: {item['price']}\nLink: {item['link']}\n\n"
        
        send_email(msg_content)

def send_email(content):
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = "🛡️ Scout: New Tier 1 Finds"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

if __name__ == "__main__":
    run_scout()
