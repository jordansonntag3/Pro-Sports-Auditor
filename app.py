import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import json

# 1. Page Configuration
st.set_page_config(page_title="Pro Sports Auditor", page_icon="🎯", layout="wide")
st.title("🎯 BANG! Button")

# 2. API & Data Loading
try:
    api_key = st.secrets["ODDS_API_KEY"]
    gemini_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Missing API Keys in Streamlit Secrets! (Need ODDS_API_KEY and GEMINI_API_KEY)")
    st.stop()

# --- AI INTELLIGENCE FUNCTION ---
def get_ai_intelligence(matchup):
    """Calls Gemini 1.5 Flash with Google Search to get live injury news."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    
    prompt = f"""
    Perform a Google Search for the latest injury reports, player rest news, and team fatigue 
    (like back-to-back games) for this matchup: {matchup}. 
    Provide a concise 1-sentence summary of the roster health and give a recommendation: 
    🟢 PLAY if the math edge is supported by news, or 🛑 HARD PASS if injuries make it a trap.
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search_retrieval": {}}]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        result = response.json()
        ai_text = result['candidates'][0]['content']['parts'][0]['text']
        return ai_text.strip()
    except Exception:
        return "⚠️ Intelligence Offline (Check API Key)"

@st.cache_data(ttl=600)
def load_opening_data():
    try: return pd.read_csv("opening_lines.csv")
    except: return pd.DataFrame()

opening_df = load_opening_data()

# 3. AUDIT SETTINGS
st.markdown("### 🛠️ Audit Settings")
col1, col2 = st.columns(2)

with col1:
    horizon = st.radio("Scan Window:", ["Today Only", "Tomorrow Only", "Next 48 Hours"], horizontal=True)
    # UPDATED SLIDER: Min 0.5, Max 1.5, Default 0.5
    min_edge = st.slider("Min. Discrepancy (Points):", 0.5, 1.5, 0.5, 0.1)

with col2:
    leagues = {
        "NBA": "basketball_nba", 
        "NHL": "icehockey_nhl", 
        "NFL": "americanfootball_nfl",
        "NCAA B": "basketball_ncaab",
        "NCAA F": "americanfootball_ncaaf"
    }
    selected_sports = st.multiselect("Select Leagues:", list(leagues.keys()), default=["NBA", "NHL", "NCAA B"])

# 4. Date Logic
local_now = datetime.utcnow() - timedelta(hours=5)
today_start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

if horizon == "Today Only": start_local, end_local = today_start_local, today_start_local + timedelta(days=1)
elif horizon == "Tomorrow Only": start_local, end_local = today_start_local + timedelta(days=1), today_start_local + timedelta(days=2)
else: start_local, end_local = today_start_local, today_start_local + timedelta(days=2)

time_from = (start_local + timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
time_to = (end_local + timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')

# 5. Engine
if st.button("🚀 RUN SCAN", use_container_width=True):
    all_results = []
    with st.spinner(f"Analyzing {horizon} markets & Fetching Intelligence..."):
        current_utc = datetime.utcnow()
        for name in selected_sports:
            url = f"https://api.the-odds-api.com/v4/sports/{leagues[name]}/odds/"
            params = {"apiKey": api_key, "regions": "us,eu", "
