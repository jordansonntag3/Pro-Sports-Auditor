import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# 1. Page Configuration
st.set_page_config(page_title="Pro Sports Auditor", page_icon="🎯", layout="wide")
st.title("🎯 The Push-Button Auditor")

# 2. Smart API Key Logic
try:
    api_key = st.secrets["ODDS_API_KEY"]
except Exception:
    api_key = "455298a2458c5781e144d28f0f8f97bc"

# 3. AUDIT SETTINGS
st.markdown("### 🛠️ Audit Settings")
col1, col2 = st.columns(2)

with col1:
    horizon = st.radio("Scan Window:", ["Today Only", "Tomorrow Only", "Next 48 Hours"], horizontal=True)
    min_edge = st.slider("Min. Discrepancy (Points):", 0.5, 3.0, 1.0, 0.5)

with col2:
    leagues = {"NBA": "basketball_nba", "NHL": "icehockey_nhl"}
    selected_sports = st.multiselect("Select Leagues:", list(leagues.keys()), default=["NBA", "NHL"])

# 4. Clean Status Metrics
st.markdown("---")
m1, m2, m3 = st.columns(3)
m1.metric("Target Window", horizon)
m2.metric("Min. Edge", f"{min_edge} pts")
m3.metric("Market Sources", "FD vs. PIN")
st.markdown("---")

# 5. Date Logic (Fixed for Central Time)
# Subtract 5 hours from UTC to match Central Daylight Time (CDT)
local_now = datetime.utcnow() - timedelta(hours=5)
# Lock to exactly 12:00 AM Central Time
today_start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

if horizon == "Today Only":
    start_local = today_start_local
    end_local = start_local + timedelta(days=1)
elif horizon == "Tomorrow Only":
    start_local = today_start_local + timedelta(days=1)
    end_local = start_local + timedelta(days=1)
else: # Next 48 Hours
    start_local = today_start_local
    end_local = start_local + timedelta(days=2)

# Convert the CDT bounds back to UTC for the API
time_from = (start_local + timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
time_to = (end_local + timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')

# 6. The Auditor Engine
if st.button("🚀 RUN SCAN", use_container_width=True):
    all_results = []
    with st.spinner(f"Analyzing {horizon} market health..."):
        for name in selected_sports:
            url = f"https://api.the-odds-api.com/v4/sports/{leagues[name]}/odds/"
            params = {
                "apiKey": api_key, 
                "regions": "us,eu", 
                "markets": "spreads", 
                "bookmakers": "fanduel,pinnacle", 
                "commenceTimeFrom": time_from, 
                "commenceTimeTo": time_to
            }
            try:
                response = requests.get(url, params=params)
                data = response.json()
                for game in data:
                    away_team = game.get('away_team')
                    home_team = game.get('home_team')
                    
                    fd_away_line, pin_away_line = None, None
                    
                    for book in game.get('bookmakers', []):
                        markets = book.get('markets', [])
                        if not markets: continue
                        
                        outcomes = markets[0].get('outcomes', [])
                        for outcome in outcomes:
                            # Isolate the away team's spread to compare apples to apples
                            if outcome.get('name') == away_team:
                                if book['key'] == 'fanduel':
                                    fd_away_line = outcome.get('point')
                                elif book['key'] == 'pinnacle':
                                    pin_away_line = outcome.get('point')
                    
                    if fd_away_line is not None and pin_away_line is not None:
                        edge = abs(fd_away_line - pin_away_line)
                        if edge >= min_edge:
                            conf = round(7.0 + (edge * 0.4), 1)
                            
                            # TARGET BET LOGIC: Determine who to bet on at FanDuel
                            if fd_away_line > pin_away_line:
                                target_team = away_team
                                target_line = fd_away_line
                            else:
                                target_team = home_team
                                target_line = -fd_away_line # The inverse line for the home team
                            
                            # Format for readability (+ and - signs)
                            def format_line(line):
                                return f"+{line}" if line > 0 else f"{line}"
                            
                            all_results.append({
                                "Target Bet": f"🟢 {target_team} {format_line(target_line)}",
                                "Matchup": f"{away_team} @ {home_team}",
                                "FanDuel Line": format_line(fd_away_line),
                                "Pinnacle Line": format_line(pin_away_line),
                                "Edge": f"{edge} pts",
                                "Confidence": f"{conf}/10",
                                "Sport": name,
                                "Start": pd.to_datetime(game['commence_time']).strftime('%m/%d %H:%M')
                            })
            except Exception as e:
                st.error(f"Scan failed for {name}: {e}")

    if all_results:
        st.success(f"🚨 Found {len(all_results)} targets for {horizon}!")
        df = pd.DataFrame(all_results)
        
        # Shift the index so it starts at 1 instead of 0
        df.index = df.index + 1
        
        st.dataframe(df, use_container_width=True)
        st.info("💡 **Intelligence Note:** Market mismatches identified. Awaiting roster health check.")
    else:
        st.warning(f"No mechanical mismatches found for {horizon}. Markets are tight.")
