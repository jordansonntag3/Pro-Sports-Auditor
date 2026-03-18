import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import json

# 1. Page Configuration
st.set_page_config(page_title="BANG! Button", page_icon="🎯", layout="wide")
st.title("🎯 BANG! Button")

# 2. API & Data Loading
try:
    api_key = st.secrets["ODDS_API_KEY"]
    gemini_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Missing API Keys! Add ODDS_API_KEY and GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

# --- AI INTELLIGENCE FUNCTION ---
def get_ai_intelligence(matchup):
    """Calls Gemini 3 Flash with live Google Search for 2026 scouting."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent?key={gemini_key}"
    
    prompt = f"""
    Search for latest injury news and roster health for: {matchup}. 
    Provide a 1-sentence summary and recommendation: 
    🟢 PLAY if supported by news, or 🛑 HARD PASS if injuries make it a trap.
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}] 
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        result = response.json()

        if response.status_code != 200:
            error_info = result.get('error', {})
            return f"❌ {response.status_code}: {error_info.get('message', 'API Error')[:30]}"

        candidates = result.get('candidates', [])
        if not candidates:
            return "⚠️ No analysis (Possible safety block)"
        
        candidate = candidates[0]
        parts = candidate.get('content', {}).get('parts', [])
        if parts and 'text' in parts[0]:
            return parts[0]['text'].strip()
        
        return "⚠️ Structure Error"
    except Exception as e:
        return f"⚠️ Connection Error: {str(e)[:30]}"

@st.cache_data(ttl=600)
def load_opening_data():
    try: return pd.read_csv("opening_lines.csv")
    except: return pd.DataFrame()

opening_df = load_opening_data()

# 3. AUD
