import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# 1. Page Configuration
st.set_page_config(page_title="Pro Sports Auditor", page_icon="🎯", layout="wide")
st.title("🎯 BANG! Button")

# 2. API & Data Loading
try:
    api_key = st.secrets["ODDS_API_KEY"]
except Exception:
    api_key = "455298a2458c5781e144d28f0f8f97bc"

@st.cache_data(ttl=600)
def load_opening_data():
    try:
        return pd.read_csv("opening_lines.csv")
    except:
        return pd.DataFrame()

opening_df = load_opening_data()

# 3. AUDIT SETTINGS
st.markdown("### 🛠️ Audit Settings")
col1, col2 = st.columns(2)

with col1:
    horizon = st.radio("Scan Window:", ["Today Only", "Tomorrow Only", "Next 48 Hours"], horizontal=True)
    min_edge = st.slider("Min. Discrepancy (Points):", 0.5, 3.0, 1.0, 0.5)

with col2:
    leagues = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NFL": "americanfootball_nfl"}
    selected_sports = st.multiselect("Select Leagues:", list(leagues.keys()), default=["NBA", "NHL"])

# 4. Date Logic
local_now = datetime.utcnow() - timedelta(hours=5)
today_start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

if horizon == "Today Only":
    start_local, end_local = today_start_local, today_start_local + timedelta(days=1)
elif horizon == "Tomorrow Only":
    start_local, end_local = today_start_local + timedelta(days=1), today_start_local + timedelta(days=2)
else:
    start_local, end_local = today_start_local, today_start_local + timedelta(days=2)

time_from = (start_local + timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
time_to = (end_local + timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')

# 5. Engine
if st.button("🚀 RUN SCAN", use_container_width=True):
    all_results = []
    with st.spinner(f"Analyzing {horizon} markets..."):
        for name in selected_sports:
            url = f"https://api.the-odds-api.com/v4/sports/{leagues[name]}/odds/"
            params = {"apiKey": api_key, "regions": "us,eu", "markets": "spreads", "bookmakers": "fanduel,pinnacle", "commenceTimeFrom": time_from, "commenceTimeTo": time_to}
            
            try:
                response = requests.get(url, params=params).json()
                for game in response:
                    away_team = game.get('away_team')
                    home_team = game.get('home_team')
                    fd_away, pin_away = None, None
                    
                    for book in game.get('bookmakers', []):
                        outcomes = book.get('markets', [{}])[0].get('outcomes', [])
                        for o in outcomes:
                            if o.get('name') == away_team:
                                if book['key'] == 'fanduel': fd_away = o.get('point')
                                elif book['key'] == 'pinnacle': pin_away = o.get('point')

                    if fd_away is not None and pin_away is not None:
                        edge = abs(fd_away - pin_away)
                        if edge >= min_edge:
                            target_team = away_team if fd_away > pin_away else home_team
                            target_line = fd_away if fd_away > pin_away else -fd_away
                            
                            # Matchup Proofing
                            teams = sorted([away_team, home_team])
                            matchup_key = f"{teams[0]} vs {teams[1]}"
                            
                            # Historical Ledger Analysis
                            movement_str = "No Morning Data"
                            if not opening_df.empty:
                                history = opening_df[opening_df['Matchup'] == matchup_key]
                                if not history.empty:
                                    true_open = history.iloc[0]['Open_Pinnacle'] # The oldest record
                                    last_scan = history.iloc[-1]['Open_Pinnacle'] # The most recent record
                                    
                                    total_move = pin_away - true_open
                                    recent_move = pin_away - last_scan
                                    
                                    movement_str = f"Total: {total_move:+.1f} | Recent: {recent_move:+.1f}"

                            def fmt(l): return f"+{l}" if l > 0 else f"{l}"
                            
                            all_results.append({
                                "Target Bet": f"🟢 {target_team} {fmt(target_line)}",
                                "Matchup": f"{away_team} @ {home_team}",
                                "Movement (PIN
