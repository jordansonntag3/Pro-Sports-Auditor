import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from io import StringIO

# 1. Page Configuration (MUST BE FIRST)
# Points to a high-res icon so Chrome/Android can see it clearly
st.set_page_config(
    page_title="BANG! Button", 
    page_icon="https://raw.githubusercontent.com/googlefonts/noto-emoji/main/png/512/emoji_u1f4a5.png", 
    layout="wide"
)

st.title("💥 BANG! Button")

# 2. Secrets Check
if "ODDS_API_KEY" not in st.secrets or "GEMINI_API_KEY" not in st.secrets:
    st.warning("⚠️ Setup Required: Add 'ODDS_API_KEY' and 'GEMINI_API_KEY' to Streamlit Secrets.")
    st.stop()

api_key = st.secrets["ODDS_API_KEY"]
gemini_key = st.secrets["GEMINI_API_KEY"]

# --- AI INTELLIGENCE FUNCTION ---
def get_ai_intelligence(matchup):
    # Updated to use the stable 2026 Gemini 3 Flash endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={gemini_key}"
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]

    prompt = f"Search for latest injury news and roster health for: {matchup}. Provide a 1-sentence summary and recommendation: 🟢 PLAY or 🛑 HARD PASS."
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "safetySettings": safety_settings 
    }
    
    try:
        time.sleep(1.2) # Quota protection
        response = requests.post(url, json=payload, timeout=20).json()
        
        if "error" in response:
            return f"⚠️ API ERROR"

        candidates = response.get('candidates', [])
        if not candidates: return "🛑 BLOCKED"

        parts = candidates[0].get('content', {}).get('parts', [])
        if parts and 'text' in parts[0]:
            return parts[0]['text'].strip()
            
        return "⚠️ NO INFO"
    except:
        return "⚠️ CONNECTION ERROR"

# --- LIVE DATA LOADING (THE FIX) ---
@st.cache_data(ttl=300) # Refreshes every 5 minutes
def load_opening_data():
    # REQUIRED: Replace 'YOUR_USER' and 'YOUR_REPO' with your actual GitHub info
    # If repo is private, ensure you have 'GITHUB_TOKEN' in st.secrets
    RAW_URL = "https://raw.githubusercontent.com/jordansonntag3/Pro-Sports-Auditor/main/opening_lines.csv"
    
    headers = {}
    if "GITHUB_TOKEN" in st.secrets:
        headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}"}
    
    try: 
        # Cache-busting parameter ensures we don't get an old version
        response = requests.get(f"{RAW_URL}?v={time.time()}", headers=headers)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.text))
            update_ts = datetime.now().strftime('%I:%M %p')
            return df, update_ts
        return pd.DataFrame(), "Fetch Failed"
    except: 
        return pd.DataFrame(), "Error"

opening_df, last_update = load_opening_data()

# --- TOP STATUS BAR ---
st.markdown(f"**🕒 App Sync:** {last_update} | **📍 Region:** Des Moines (Central)")
st.divider()

# 3. AUDIT SETTINGS
with st.expander("🛠️ Audit & Display Settings", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        view_mode = st.radio("View Mode:", ["Mobile Cards", "Desktop Table"], horizontal=True)
        horizon = st.radio("Scan Window:", ["Today", "Tomorrow", "Next 48 Hours"], horizontal=True)
    with col2:
        min_edge = st.slider("Min. Discrepancy (Points):", 0.5, 2.0, 0.5, 0.5)
        leagues = {"NBA": "basketball_nba", "NHL": "icehockey_nhl", "NCAA B": "basketball_ncaab"}
        selected_sports = st.multiselect("Leagues:", list(leagues.keys()), default=["NBA"])

# 4. ENGINE
if st.button("🚀 RUN SCAN", use_container_width=True):
    all_results = []
    status_msg = st.empty()
    
    now_utc = datetime.utcnow()
    # Central Time Adjustment
    time_from = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    if horizon == "Today":
        time_to = (now_utc + timedelta(hours=18)).strftime('%Y-%m-%dT%H:%M:%SZ')
    elif horizon == "Tomorrow":
        time_to = (now_utc + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
    else: 
        time_to = (now_utc + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M:%SZ')

    with st.spinner("Analyzing Markets..."):
        for name in selected_sports:
            status_msg.info(f"Scanning {name}...")
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
                                    move_str = f"Move: {tot:+.1f} pts"

                            def fmt(l): return f"+{l}" if l > 0 else f"{l}"
                            intel_report = get_ai_intelligence(f"{away_team} vs {home_team}")
                            
                            is_trap = any(x in intel_report.upper() for x in ["🛑", "HARD PASS", "OUT", "INJURY"])
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
                    st.caption(f"🕒 {res['Start']} | {res['Matchup']}")
                    colA, colB = st.columns(2)
                    colA.metric("Edge", res['Edge'], res['Move'] if "No" not in res['Move'] else None)
                    colB.metric("FD/PIN", f"{res['FD']}/{res['PIN']}")
                    st.info(f"**Report:** {res['Intel']}")
        else:
            st.dataframe(pd.DataFrame(all_results), use_container_width=True, hide_index=True)
    else: 
        st.warning("No discrepancies found.")
