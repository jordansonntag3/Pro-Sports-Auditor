import streamlit as st
import requests
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="Pro Sports Auditor", page_icon="🎯", layout="wide")
st.title("🎯 The Push-Button Auditor")
st.markdown("### High-Confidence Market Discrepancies (FanDuel vs. Pinnacle)")

# 2. HARDCODED API KEY (Your Secret Key)
api_key = "455298a2458c5781e144d28f0f8f97bc"

# 3. Friendly Names Mapping
leagues = {
    "NBA": "basketball_nba",
    "NHL": "icehockey_nhl",
    "NFL": "americanfootball_nfl"
}

selected_friendly_names = st.multiselect(
    "Select Leagues to Audit:",
    options=list(leagues.keys()),
    default=["NBA", "NHL"]
)

# 4. Execution
if st.button("Find All Bets"):
    all_results = []
    
    with st.spinner("Scanning Pro Markets..."):
        for name in selected_friendly_names:
            sport_slug = leagues[name]
            url = f"https://api.the-odds-api.com/v4/sports/{sport_slug}/odds/"
            params = {
                "apiKey": api_key,
                "regions": "us,eu",
                "markets": "spreads",
                "bookmakers": "fanduel,pinnacle"
            }
            
            try:
                response = requests.get(url, params=params)
                data = response.json()
                
                if response.status_code == 200:
                    for game in data:
                        fd_line, pin_line = None, None
                        
                        for book in game.get('bookmakers', []):
                            if book['key'] == 'fanduel':
                                try:
                                    fd_line = book['markets'][0]['outcomes'][0].get('point')
                                except: pass
                            elif book['key'] == 'pinnacle':
                                try:
                                    pin_line = book['markets'][0]['outcomes'][0].get('point')
                                except: pass
                        
                        if fd_line is not None and pin_line is not None:
                            edge = abs(fd_line - pin_line)
                            # Only show bets with at least a 1.5 point mismatch
                            if edge >= 1.5:
                                all_results.append({
                                    "Sport": name,
                                    "Matchup": f"{game['away_team']} @ {game['home_team']}",
                                    "FanDuel": fd_line,
                                    "Pinnacle": pin_line,
                                    "Edge": f"{edge} pts",
                                    "Start Time": pd.to_datetime(game['commence_time']).strftime('%m/%d %H:%M')
                                })
                else:
                    st.error(f"API Error for {name}: {data.get('message', 'Unknown')}")
            except Exception as e:
                st.error(f"System Error scanning {name}: {e}")

    if all_results:
        st.success(f"🚨 Found {len(all_results)} targeted bets!")
        st.table(pd.DataFrame(all_results))
    else:
        st.info("No math-backed discrepancies found right now. Check back when the markets move!")