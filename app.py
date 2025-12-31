import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# GUI Setup
st.set_page_config(page_title="Scout: Tier 1 Collector", page_icon="🛡️")
st.title("🛡️ Scout: Collector Agent")
st.subheader("Monitoring Tier 1, LE, and Historical Artifacts")

# Sidebar - Where you input your targets
st.sidebar.header("Target Settings")
targets = [
    "Texas Ranger Silver Peso Badge", 
    "OHP obsolete oval patch", 
    "WHCA challenge coin authentic",
    "Quantrill Raiders"
]
selected_target = st.sidebar.selectbox("Select Target to Scout", targets)
custom_target = st.sidebar.text_input("Or type a custom hunt:")

# The "Brain" - Searching eBay
def scout_ebay(query):
    search_term = custom_target if custom_target else query
    url = f"https://www.ebay.com/sch/i.html?_nkw={search_term.replace(' ', '+')}&_sop=10"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        listings = []
        
        for item in soup.select('.s-item__info')[1:15]: # Limit to top 14
            title = item.select_one('.s-item__title').text
            price = item.select_one('.s-item__price').text
            link = item.select_one('.s-item__link')['href']
            
            # Exclusion Logic
            if "replica" not in title.lower() and "repro" not in title.lower():
                listings.append({
                    "Site": "eBay",
                    "Item": title,
                    "Cost": price,
                    "Link": link
                })
        return listings
    except Exception as e:
        return [{"Error": str(e)}]

# Running the Scout
if st.button('📡 Start Scout'):
    with st.spinner(f'Scouting for {selected_target}...'):
        results = scout_ebay(selected_target)
        if results:
            df = pd.DataFrame(results)
            # Make the Link clickable in the table
            st.dataframe(df, column_config={
                "Link": st.column_config.Link_Column("View Listing")
            })
        else:
            st.warning("No authentic items found in current sweep.")

st.divider()
st.caption("Scout v1.0 | Data sourced from live auctions. Remember to verify provenance.")
