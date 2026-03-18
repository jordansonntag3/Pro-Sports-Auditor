import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import time
import random

# 1. Page Configuration
st.set_page_config(page_title="BANG! Button", page_icon="🎯", layout="wide")
st.title("🎯 BANG! Button")

# 2. API & Data Loading
if "ODDS_API_KEY" not in st.secrets or "GEMINI_API_KEY" not in st.secrets:
    st.warning("⚠️ Setup Required: Please add 'ODDS_API_KEY' and 'GEMINI_API_KEY' to your Streamlit Secrets.")
    st.stop()

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- OPTIMIZED: AI INTELLIGENCE FUNCTION ---
def get_ai_intelligence(matchup):
    """Calls Gemini with a small 'Patience' delay to prevent Busy errors."""
    # Using the rock-solid March 2026 stable endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    
    prompt = f"""
    Search for latest injury news and roster health for: {matchup}. 
    Provide a 1-sentence summary and recommendation: 
    🟢 PLAY if supported by news, or 🛑 HARD PASS if injuries make it a trap.
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}] 
    }
    
    # Add a tiny random delay (0.5 to 1.5 seconds) so we don't spam the API
    time.sleep(random.uniform(0.5, 1.5))
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        result = response.json()
        
        candidates = result.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            if parts and 'text' in parts[0]:
                return parts[0]['text'].strip()
            # If the AI was blocked by a safety filter, it will tell us why here
            elif 'finishReason' in candidates[0]:
                return f"🛑 Safety Filter: {candidates[0]['finishReason']}"
        
        return "⚠️ Intelligence Busy (Try scanning again in 10 seconds)"
    except Exception:
        return "⚠️ Connection Timed Out"

@st.cache_data(ttl=600)
def load_opening_data():
    try: return pd.read_csv("opening_lines.csv")
    except: return pd.DataFrame()

opening_df = load_opening_data()

# 3. AUDIT SETTINGS (Main Page for Mobile)
with st.expander("🛠️ Audit & Display Settings", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        view_mode = st.radio("View Mode:", ["Mobile Cards", "Desktop Table"], horizontal=True)
        horizon = st.radio("Scan Window:", ["Today Only", "Tomorrow Only", "Next 48 Hours"], horizontal=True)
    with col2:
        min_edge = st.slider("Min. Discrepancy (Points):", 0.5, 1.5, 0.5, 0.1)
        leagues = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab"}
        selected_sports = st.multiselect("Leagues:", list(leagues.keys()), default=["NBA", "NHL", "NCAA B"])

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
    with st.spinner("Analyzing Markets & Scouting Injuries..."):
        current_utc = datetime.utcnow()
        for name in selected_sports:
            url = f"https://api.the-odds-api.com/v4/sports/{leagues[name]}/odds/"
            params = {"apiKey": api_key, "regions": "us,eu", "markets": "spreads", "bookmakers": "fanduel,pinnacle", "commenceTimeFrom": time_from, "commenceTimeTo": time_to}
            
            try:
                response = requests.get(url, params=params).json()
                for game in response:
                    game_start_utc = datetime.strptime(game['commence_time'], '%Y-%m-%dT%H:%M:%SZ')
                    if game_start_utc < current_utc: continue 

                    away_team, home_team = game.get('away_team'), game.get('home_team')
                    fd_away, pin_away = None, None
                    for book in game.get('bookmakers', []):
                        outcomes = book.get('markets', [{}])[0].get('outcomes', [])
                        for o in outcomes:
                            if o.get('name') == away_team:
                                if book['key'] == 'fanduel': fd_away = o.get('point')
                                elif book['key'] == 'pinnacle': pin_away = o.get('point')

                    if fd_away is not None and pin_away is not None:
                        edge_val = abs(fd_away - pin_away)
                        if edge_val >= (min_edge - 0.01):
                            teams = sorted([away_team, home_team])
                            matchup_key = f"{teams[0]} vs {teams[1]}"
                            
                            move_str = "No Morning Data"
                            if not opening_df.empty:
                                hist = opening_df[opening_df['Matchup'] == matchup_key]
                                if not hist.empty:
                                    tot = pin_away - hist.iloc[0]['Open_Pinnacle']
                                    rec = pin_away - hist.iloc[-1]['Open_Pinnacle']
                                    move_str = f"Tot: {tot:+.1f} | Rec: {rec:+.1f}"

                            all_results.append({
                                "Target": f"{away_team if fd_away > pin_away else home_team} {f'+{fd_away}' if (fd_away if fd_away > pin_away else -fd_away) > 0 else (fd_away if fd_away > pin_away else -fd_away)}",
                                "Matchup": f"{away_team} @ {home_team}",
                                "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p'),
                                "Move": move_str,
                                "FD": fd_away,
                                "PIN": pin_away,
                                "Edge": f"{edge_val:.1f} pts",
                                "Intel": get_ai_intelligence(f"{away_team} vs {home_team}")
                            })
            except: pass

    if all_results:
        st.success(f"🚨 Found {len(all_results)} targets!")
        if view_mode == "Mobile Cards":
            for res in all_results:
                with st.container(border=True):
                    st.subheader(f"🟢 {res['Target']}")
                    st.caption(f"🕒 {res['Start']} | {res['Matchup']}")
                    s1, s2, s3 = st.columns(3)
                    s1.metric("Edge", res['Edge'])
                    s2.metric("FD/PIN", f"{res['FD']}/{res['PIN']}")
                    s3.caption(f"**Move**\n{res['Move']}")
                    st.info(f"**Scouting Report:**\n{res['Intel']}")
        else:
            df = pd.DataFrame(all_results)
            st.dataframe(df, use_container_width=True)
    else: 
        st.warning("No mechanical mismatches found. Try lowering the Min. Discrepancy.")
