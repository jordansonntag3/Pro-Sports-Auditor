import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os

# 1. Page Configuration
st.set_page_config(page_title="BANG! Button", page_icon="🎯", layout="wide")
st.title("🎯 BANG! Button")

# 2. Secrets Check
if "ODDS_API_KEY" not in st.secrets or "GEMINI_API_KEY" not in st.secrets:
    st.warning("⚠️ Setup Required: Add 'ODDS_API_KEY' and 'GEMINI_API_KEY' to Streamlit Secrets.")
    st.stop()

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- AI INTELLIGENCE FUNCTION ---
def get_ai_intelligence(matchup):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={gemini_key}"
    safety_settings = [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
    prompt = f"Search for latest injury news and roster health for: {matchup}. Provide a 1-sentence summary and recommendation: 🟢 PLAY or 🛑 HARD PASS."
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "safetySettings": safety_settings 
    }
    try:
        time.sleep(1.5) 
        response = requests.post(url, json=payload, timeout=20).json()
        candidates = response.get('candidates', [])
        if candidates:
            return candidates[0].get('content', {}).get('parts', [])[0]['text'].strip()
        return "⚠️ Intelligence Busy"
    except:
        return "⚠️ Connection Error"

@st.cache_data(ttl=600)
def load_opening_data():
    try: 
        df = pd.read_csv("opening_lines.csv")
        mod_time = os.path.getmtime("opening_lines.csv")
        snapshot_time = datetime.fromtimestamp(mod_time).strftime('%I:%M %p')
        return df, snapshot_time
    except: 
        return pd.DataFrame(), "N/A"

opening_df, last_update = load_opening_data()

# --- TOP STATUS BAR ---
st.markdown(f"**🕒 Last Snapshot:** {last_update} Central | **📍 Timezone:** Central Time (Des Moines)")
st.divider()

# 3. AUDIT SETTINGS
with st.expander("🛠️ Audit & Display Settings", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        view_mode = st.radio("View Mode:", ["Mobile Cards", "Desktop Table"], horizontal=True)
        # --- NEW SCAN WINDOW OPTIONS ---
        horizon = st.radio("Scan Window:", ["Today", "Tomorrow", "2 Days Out", "Next 48 Hours"], horizontal=True)
    with col2:
        min_edge = st.slider("Min. Discrepancy (Points):", 0.5, 1.5, 0.5, 0.1)
        leagues = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab"}
        selected_sports = st.multiselect("Leagues:", list(leagues.keys()), default=["NBA", "NCAA B"])

# 4. Engine
if st.button("🚀 RUN SCAN", use_container_width=True):
    all_results = []
    status_msg = st.empty()
    
    # --- DYNAMIC DATE LOGIC ---
    now_utc = datetime.utcnow()
    local_now = now_utc - timedelta(hours=5)
    today_start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if horizon == "Today":
        time_from = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        time_to = (today_start_local + timedelta(days=1, hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    elif horizon == "Tomorrow":
        time_from = (today_start_local + timedelta(days=1, hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
        time_to = (today_start_local + timedelta(days=2, hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
    elif horizon == "2 Days Out":
        time_from = (today_start_local + timedelta(days=2, hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
        time_to = (today_start_local + timedelta(days=3, hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
    else: # Next 48 Hours
        time_from = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        time_to = (now_utc + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M:%SZ')

    with st.spinner("Analyzing Markets..."):
        for name in selected_sports:
            status_msg.info(f"Scanning {name}...")
            url = f"https://api.the-odds-api.com/v4/sports/{leagues[name]}/odds/"
            params = {"apiKey": api_key, "regions": "us,eu", "markets": "spreads", "bookmakers": "fanduel,pinnacle", "commenceTimeFrom": time_from, "commenceTimeTo": time_to}
            
            try:
                data = requests.get(url, params=params).json()
                for game in data:
                    away_team, home_team = game.get('away_team'), game.get('home_team')
                    fd_away, pin_away = None, None
                    for book in game.get('bookmakers', []):
                        markets = book.get('markets', [])
                        if not markets: continue
                        outcomes = markets[0].get('outcomes', [])
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

                            def fmt(l): return f"+{l}" if l > 0 else f"{l}"
                            intel_report = get_ai_intelligence(f"{away_team} vs {home_team}")
                            
                            is_trap = any(x in intel_report.upper() for x in ["🛑", "HARD PASS", "TRAP", "OUT", "INJURY"])
                            status_emoji = "🔴" if is_trap else "🟢"
                            
                            all_results.append({
                                "Status": status_emoji,
                                "Target": f"{away_team if fd_away > pin_away else home_team} {fmt(fd_away if fd_away > pin_away else -fd_away)}",
                                "Matchup": f"{away_team} @ {home_team}",
                                "Start": (pd.to_datetime(game['commence_time']) - pd.Timedelta(hours=5)).strftime('%m/%d %I:%M %p'),
                                "Move": move_str,
                                "FD": fmt(fd_away), "PIN": fmt(pin_away), "Edge": f"{edge_val:.1f} pts",
                                "Intel": intel_report
                            })
            except: pass

    status_msg.empty()

    if all_results:
        st.success(f"🚨 Found {len(all_results)} targets!")
        if view_mode == "Mobile Cards":
            for res in all_results:
                with st.container(border=True):
                    st.subheader(f"{res['Status']} {res['Target']}")
                    st.caption(f"🕒 {res['Start']} | Match: {res['Matchup']}")
                    s1, s2, s3 = st.columns(3)
                    s1.metric("Edge", res['Edge'])
                    s2.metric("FD/PIN", f"{res['FD']}/{res['PIN']}")
                    s3.caption(f"**Move**\n{res['Move']}")
                    
                    if res['Status'] == "🔴":
                        st.error(f"**Scouting Report:**\n{res['Intel']}")
                    else:
                        st.info(f"**Scouting Report:**\n{res['Intel']}")
        else:
            st.dataframe(pd.DataFrame(all_results)[['Status', 'Target', 'Matchup', 'Start', 'Edge', 'FD', 'PIN', 'Move', 'Intel']], use_container_width=True, hide_index=True)
    else: 
        st.warning(f"No mechanical mismatches found for {horizon.lower()}.")
