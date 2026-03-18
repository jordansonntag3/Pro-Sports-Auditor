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
    st.error("Missing API Keys in Streamlit Secrets!")
    st.stop()

# --- NEW: AI INTELLIGENCE FUNCTION ---
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
        "tools": [{"google_search_retrieval": {}}] # This triggers the live web search
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        result = response.json()
        # Extracting the text response from Gemini
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
    min_edge = st.slider("Min. Discrepancy (Points):", 1.0, 3.0, 1.0, 0.5)

with col2:
    leagues = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NFL": "americanfootball_nfl", "NCAA B": "basketball_ncaab", "NCAA F": "americanfootball_ncaaf"}
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
                        if edge_val >= min_edge:
                            target_team = away_team if fd_away > pin_away else home_team
                            target_line = fd_away if fd_away > pin_away else -fd_away
                            teams = sorted([away_team, home_team])
                            matchup_key = f"{teams[0]} vs {teams[1]}"
                            
                            movement_str = "No Morning Data"
                            if not opening_df.empty:
                                history = opening_df[opening_df['Matchup'] == matchup_key]
                                if not history.empty:
                                    total_move = pin_away - history.iloc[0]['Open_Pinnacle']
                                    recent_move = pin_away - history.iloc[-1]['Open_Pinnacle']
                                    movement_str = f"{total_move:+.1f} | {recent_move:+.1f}"

                            def fmt(l): return f"+{l}" if l > 0 else f"{l}"
                            
                            # ONLY CALL AI IF THERE IS A VALID EDGE
                            intel = get_ai_intelligence(f"{away_team} vs {home_team}")

                            all_results.append({
                                "Target": f"🟢 {target_team} {fmt(target_line)}",
                                "Matchup": f"{away_team} @ {home_team}",
                                "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p'),
                                "Move": movement_str,
                                "FD": fmt(fd_away),
                                "PIN": fmt(pin_away),
                                "Edge": f"{edge_val} pts",
                                "Intelligence": intel
                            })
            except: pass

    if all_results:
        st.success(f"🚨 Found {len(all_results)} targets!")
        df = pd.DataFrame(all_results)
        st.dataframe(
            df, 
            use_container_width=True,
            column_config={
                "Target": st.column_config.TextColumn(width="small"),
                "Matchup": st.column_config.TextColumn(width="medium"),
                "Start": st.column_config.TextColumn(width="small"),
                "Move": st.column_config.TextColumn(width="small"),
                "FD": st.column_config.TextColumn(width="small"),
                "PIN": st.column_config.TextColumn(width="small"),
                "Edge": st.column_config.TextColumn(width="small"),
                "Intelligence": st.column_config.TextColumn(width="large")
            }
        )
    else: st.warning(f"No mechanical mismatches found for {horizon}.")
